from __future__ import annotations

import base64
import asyncio
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

try:
    from astrbot.core.star.star import StarMetadata

    if not hasattr(StarMetadata, "pages"):
        StarMetadata.pages = []
except Exception:
    pass


VOLC_FLASH_ENDPOINT = (
    "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
)
VOLC_RESOURCE_ID = "volc.bigasr.auc_turbo"
VOLC_SUCCESS_CODE = "20000000"
VOLC_SILENT_AUDIO_CODE = "20000003"
SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".opus"}
TRANSCODE_HINT_EXTS = {".amr", ".silk", ".slk", ".m4a", ".aac", ".flac", ".webm"}


class UserVisibleError(Exception):
    """An error that can be safely shown in a chat reply."""


class VolcAsrError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: str = "",
        logid: str = "",
        request_id: str = "",
        body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.logid = logid
        self.request_id = request_id
        self.body = body or {}


@dataclass(slots=True)
class AsrResult:
    text: str
    request_id: str
    logid: str = ""
    duration_ms: int | None = None
    raw: dict[str, Any] | None = None


def _config_str(config: AstrBotConfig, key: str, default: str = "") -> str:
    value = config.get(key, default)
    if value is None:
        return default
    return str(value).strip()


def _config_bool(config: AstrBotConfig, key: str, default: bool = False) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}
    return bool(value)


def _config_int(config: AstrBotConfig, key: str, default: int = 0) -> int:
    value = config.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_record_component(component: Any) -> bool:
    if isinstance(component, Comp.Record):
        return True
    component_type = getattr(component, "type", "")
    type_value = getattr(component_type, "value", component_type)
    return str(type_value).lower() == "record"


def _extract_record_sources(record: Any) -> list[str]:
    sources: list[str] = []
    for attr in ("file", "url", "path"):
        value = getattr(record, attr, None)
        if value:
            source = str(value).strip()
            if source and source not in sources:
                sources.append(source)
    return sources


def _source_to_local_path(source: str) -> Path | None:
    if not source:
        return None
    path_text = source
    if source.startswith("file://"):
        path_text = source[7:]
    elif source.startswith(("http://", "https://", "base64://")):
        return None

    path_text = unquote(path_text)
    if os.name == "nt" and len(path_text) > 2 and path_text[0] == "/" and path_text[2] == ":":
        path_text = path_text[1:]

    path = Path(path_text)
    if path.exists() and path.is_file():
        return path
    return None


def _source_suffix(source: str) -> str:
    if not source:
        return ""
    parsed_path = urlparse(source).path if source.startswith(("http://", "https://")) else source
    return Path(unquote(parsed_path)).suffix.lower()


def _detect_audio_suffix(data: bytes, source: str = "") -> str:
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return ".wav"
    if data.startswith(b"OggS"):
        return ".ogg"
    if data.startswith(b"ID3") or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return ".mp3"
    if data.startswith(b"#!AMR"):
        return ".amr"
    if data.startswith(b"#!SILK"):
        return ".silk"
    return _source_suffix(source)


def _estimate_base64_size(base64_text: str) -> int:
    cleaned = base64_text.strip()
    padding = cleaned[-2:].count("=")
    return max(0, (len(cleaned) * 3 // 4) - padding)


def _format_with_fallback(template: str, values: dict[str, Any]) -> str:
    try:
        return template.format(**values)
    except (KeyError, ValueError, IndexError):
        return str(values.get("text", ""))


class VolcBigModelAsrClient:
    def __init__(self, config: AstrBotConfig) -> None:
        self.api_key = _config_str(config, "api_key")
        self.app_key = _config_str(config, "app_key")
        self.access_key = _config_str(config, "access_key")
        self.resource_id = _config_str(config, "resource_id", VOLC_RESOURCE_ID) or VOLC_RESOURCE_ID
        self.endpoint = _config_str(config, "endpoint", VOLC_FLASH_ENDPOINT) or VOLC_FLASH_ENDPOINT
        self.uid = _config_str(config, "uid") or self.api_key or self.app_key or "astrbot"
        self.timeout_seconds = max(5, _config_int(config, "timeout_seconds", 60))
        self.enable_itn = _config_bool(config, "enable_itn", True)
        self.enable_punc = _config_bool(config, "enable_punc", True)
        self.enable_ddc = _config_bool(config, "enable_ddc", True)
        self.enable_speaker_info = _config_bool(config, "enable_speaker_info", False)
        timeout = httpx.Timeout(self.timeout_seconds, connect=10.0)
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    def validate(self) -> str:
        if self.api_key:
            return ""
        if self.app_key and self.access_key:
            return ""
        return "火山引擎 ASR 未配置：请填写 api_key，或同时填写 app_key 和 access_key。"

    async def close(self) -> None:
        await self._client.aclose()

    async def recognize(self, audio: dict[str, str]) -> AsrResult:
        request_id = str(uuid.uuid4())
        headers = {
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": request_id,
            "X-Api-Sequence": "-1",
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        else:
            headers["X-Api-App-Key"] = self.app_key
            headers["X-Api-Access-Key"] = self.access_key

        payload = {
            "user": {"uid": self.uid},
            "audio": audio,
            "request": {
                "model_name": "bigmodel",
                "enable_itn": self.enable_itn,
                "enable_punc": self.enable_punc,
                "enable_ddc": self.enable_ddc,
                "enable_speaker_info": self.enable_speaker_info,
            },
        }

        try:
            response = await self._client.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VolcAsrError(
                f"火山引擎 ASR 请求失败：{exc}",
                request_id=request_id,
            ) from exc

        status_code = response.headers.get("X-Api-Status-Code", "")
        status_message = response.headers.get("X-Api-Message", "")
        logid = response.headers.get("X-Tt-Logid", "")
        try:
            body = response.json()
        except ValueError as exc:
            raise VolcAsrError(
                "火山引擎 ASR 返回了非 JSON 响应。",
                status_code=status_code,
                logid=logid,
                request_id=request_id,
            ) from exc

        if status_code != VOLC_SUCCESS_CODE:
            message = status_message or body.get("message") or body.get("error") or "识别失败"
            raise VolcAsrError(
                f"火山引擎 ASR 识别失败：{message}",
                status_code=status_code,
                logid=logid,
                request_id=request_id,
                body=body,
            )

        text, duration_ms = self._parse_result(body)
        return AsrResult(
            text=text,
            request_id=request_id,
            logid=logid,
            duration_ms=duration_ms,
            raw=body,
        )

    @staticmethod
    def _parse_result(body: dict[str, Any]) -> tuple[str, int | None]:
        result = body.get("result") or {}
        text = str(result.get("text") or "").strip()
        if not text:
            utterances = result.get("utterances") or []
            text = "".join(str(item.get("text") or "") for item in utterances).strip()

        duration: Any = (body.get("audio_info") or {}).get("duration")
        if duration is None:
            duration = (result.get("additions") or {}).get("duration")
        try:
            duration_ms = int(duration)
        except (TypeError, ValueError):
            duration_ms = None

        return text, duration_ms


class VolcengineAsrPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.client = VolcBigModelAsrClient(config)
        self.auto_recognize = _config_bool(config, "auto_recognize", True)
        self.enable_private = _config_bool(config, "enable_private", True)
        self.enable_group = _config_bool(config, "enable_group", True)
        self.only_when_at_or_wake = _config_bool(config, "only_when_at_or_wake", False)
        self.ignore_self = _config_bool(config, "ignore_self", True)
        self.stop_event_after_recognition = _config_bool(
            config,
            "stop_event_after_recognition",
            True,
        )
        self.send_empty_result_message = _config_bool(config, "send_empty_result_message", True)
        self.notify_config_error = _config_bool(config, "notify_config_error", True)
        self.notify_asr_error = _config_bool(config, "notify_asr_error", True)
        self.show_logid = _config_bool(config, "show_logid", False)
        self.submit_mode = _config_str(config, "submit_mode", "base64").lower()
        self.reply_template = _config_str(config, "reply_template", "语音转文字：{text}")
        self.max_audio_bytes = max(1, _config_int(config, "max_audio_mb", 20)) * 1024 * 1024

    @filter.command("volc_asr_status", alias={"火山语音状态"})
    async def volc_asr_status(self, event: AstrMessageEvent):
        """查看火山引擎语音识别插件配置状态。"""
        auth_status = "已配置" if not self.client.validate() else "未配置"
        mode = "URL 直传" if self.submit_mode == "url" else "Base64 上传"
        yield event.plain_result(
            "火山引擎语音识别插件状态："
            f"\n鉴权：{auth_status}"
            f"\n提交方式：{mode}"
            f"\n私聊：{'启用' if self.enable_private else '关闭'}"
            f"\n群聊：{'启用' if self.enable_group else '关闭'}"
            f"\n最大音频：{self.max_audio_bytes // 1024 // 1024} MB"
        )

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """自动识别消息中的语音段，并直接回复文字。"""
        if not self.auto_recognize or not self._allow_event(event):
            return

        records = self._find_records(event)
        if not records:
            return

        config_error = self.client.validate()
        if config_error:
            logger.warning(config_error)
            if self.notify_config_error:
                yield event.plain_result(config_error)
            if self.stop_event_after_recognition:
                event.stop_event()
            return

        results: list[AsrResult] = []
        errors: list[str] = []
        for index, record in enumerate(records, start=1):
            try:
                audio = await self._build_audio_payload(record)
                result = await self.client.recognize(audio)
                if result.text:
                    results.append(result)
                elif self.send_empty_result_message:
                    errors.append(f"第 {index} 条语音未识别到有效内容。")
            except UserVisibleError as exc:
                logger.warning(f"语音识别准备失败：{exc}")
                if self.notify_asr_error:
                    errors.append(f"第 {index} 条语音处理失败：{exc}")
            except VolcAsrError as exc:
                logger.warning(
                    "火山引擎 ASR 失败："
                    f"status={exc.status_code} "
                    f"logid={exc.logid} "
                    f"request_id={exc.request_id} "
                    f"error={exc}"
                )
                if exc.status_code == VOLC_SILENT_AUDIO_CODE:
                    if self.send_empty_result_message:
                        errors.append(f"第 {index} 条语音是静音音频。")
                elif self.notify_asr_error:
                    detail = str(exc)
                    if self.show_logid and exc.logid:
                        detail = f"{detail}（logid: {exc.logid}）"
                    errors.append(f"第 {index} 条语音识别失败：{detail}")
            except Exception:
                logger.exception("语音识别出现未预期异常")
                if self.notify_asr_error:
                    errors.append(f"第 {index} 条语音识别失败：插件内部异常。")

        reply = self._build_reply(results, errors)
        if reply:
            yield event.plain_result(reply)

        if self.stop_event_after_recognition:
            event.stop_event()

    async def terminate(self) -> None:
        await self.client.close()

    def _allow_event(self, event: AstrMessageEvent) -> bool:
        message_obj = getattr(event, "message_obj", None)
        is_group = bool(getattr(message_obj, "group_id", ""))
        if is_group and not self.enable_group:
            return False
        if not is_group and not self.enable_private:
            return False
        if self.only_when_at_or_wake and not getattr(event, "is_at_or_wake_command", False):
            return False
        if self.ignore_self and self._is_self_message(event):
            return False
        return True

    @staticmethod
    def _find_records(event: AstrMessageEvent) -> list[Any]:
        message_obj = getattr(event, "message_obj", None)
        chain = getattr(message_obj, "message", []) or []
        return [component for component in chain if _is_record_component(component)]

    @staticmethod
    def _is_self_message(event: AstrMessageEvent) -> bool:
        message_obj = getattr(event, "message_obj", None)
        sender = getattr(message_obj, "sender", None)
        sender_id = (
            getattr(sender, "user_id", None)
            or getattr(sender, "sender_id", None)
            or getattr(sender, "id", None)
        )
        self_id = getattr(message_obj, "self_id", None)
        return bool(sender_id and self_id and str(sender_id) == str(self_id))

    async def _build_audio_payload(self, record: Any) -> dict[str, str]:
        sources = _extract_record_sources(record)
        if self.submit_mode == "url":
            for source in sources:
                if source.startswith(("http://", "https://")):
                    return {"url": source}

        base64_audio = await self._record_to_base64(record, sources)
        audio_size = _estimate_base64_size(base64_audio)
        if audio_size > self.max_audio_bytes:
            max_mb = self.max_audio_bytes // 1024 // 1024
            raise UserVisibleError(f"音频超过配置上限 {max_mb} MB。")
        return {"data": base64_audio}

    async def _record_to_base64(self, record: Any, sources: list[str]) -> str:
        last_error: Exception | None = None
        for source in sources:
            try:
                if source.startswith("base64://"):
                    return source.removeprefix("base64://")

                local_path = _source_to_local_path(source)
                if local_path is not None:
                    return await self._file_to_base64(local_path)

                if source.startswith(("http://", "https://")):
                    return await self._download_to_base64(source)
            except UserVisibleError as exc:
                last_error = exc

        convert_to_base64 = getattr(record, "convert_to_base64", None)
        if callable(convert_to_base64):
            try:
                base64_audio = await convert_to_base64()
                return str(base64_audio).removeprefix("base64://")
            except Exception as exc:
                last_error = exc

        if last_error:
            raise UserVisibleError(str(last_error)) from last_error
        raise UserVisibleError("无法从消息中读取语音文件。")

    async def _file_to_base64(self, path: Path) -> str:
        size = path.stat().st_size
        if size > self.max_audio_bytes:
            max_mb = self.max_audio_bytes // 1024 // 1024
            raise UserVisibleError(f"音频超过配置上限 {max_mb} MB。")
        data = await self._read_bytes(path)
        return base64.b64encode(data).decode("ascii")

    async def _download_to_base64(self, url: str) -> str:
        chunks: list[bytes] = []
        total = 0
        timeout = httpx.Timeout(self.client.timeout_seconds, connect=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self.max_audio_bytes:
                            max_mb = self.max_audio_bytes // 1024 // 1024
                            raise UserVisibleError(f"音频超过配置上限 {max_mb} MB。")
                        chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise UserVisibleError(f"下载语音文件失败：{exc}") from exc
        if not chunks:
            raise UserVisibleError("语音文件为空。")
        return base64.b64encode(b"".join(chunks)).decode("ascii")

    @staticmethod
    async def _read_bytes(path: Path) -> bytes:
        import asyncio

        return await asyncio.to_thread(path.read_bytes)

    def _build_reply(self, results: list[AsrResult], errors: list[str]) -> str:
        parts: list[str] = []
        if results:
            if len(results) == 1:
                text = results[0].text
                values = {
                    "text": text,
                    "logid": results[0].logid,
                    "request_id": results[0].request_id,
                    "duration_ms": results[0].duration_ms or "",
                }
            else:
                text = "\n".join(f"{index}. {item.text}" for index, item in enumerate(results, start=1))
                values = {
                    "text": text,
                    "logid": ",".join(item.logid for item in results if item.logid),
                    "request_id": ",".join(item.request_id for item in results),
                    "duration_ms": "",
                }
            parts.append(_format_with_fallback(self.reply_template, values))
            if self.show_logid:
                logids = [item.logid for item in results if item.logid]
                if logids:
                    parts.append("logid: " + ", ".join(logids))

        if errors:
            parts.extend(errors)

        return "\n".join(part for part in parts if part).strip()
