from __future__ import annotations

import base64
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx

import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star

from . import ffmpeg_locator as _ffmpeg_locator
from .emotion_engine import (
    DEFAULT_EMOTION_PROMPT_TEMPLATE,
    DEFAULT_EMOTION_WEIGHTING_POLICY,
    EMOTION_LABEL_NAMES,
    EMOTION_LABELS,
    DefaultEmotionEngine,
    DefaultEmotionLabeler,
    DefaultEmotionPromptBuilder,
    DefaultEmotionScorer,
    DefaultEmotionWeightingPolicy,
    EmotionAnalyzer,
    EmotionCoordinateMapper,
    EmotionHistoryRecord,
    EmotionJudgement,
    EmotionLabeler,
    EmotionPromptBuilder,
    EmotionScorer,
    EmotionWeightingInput,
    EmotionWeightingPolicy,
    RussellCoordinateMapper,
    append_compact_emotion_guidance as _append_compact_emotion_guidance,
    append_emotion_guidance as _append_emotion_guidance,
    build_emotion_judgement as _build_emotion_judgement,
    build_emotion_prompt as _build_emotion_prompt,
    clamp_float as _clamp_float,
    compute_emotion_respect_weight as _compute_emotion_respect_weight,
    entropy_certainty as _entropy_certainty,
    format_compact_emotion_guidance_for_llm as _format_compact_emotion_guidance_for_llm,
    format_emotion_guidance_for_llm as _format_emotion_guidance_for_llm,
    normalize_emotion_weights as _normalize_emotion_weights,
    render_named_placeholders as _render_named_placeholders,
    safe_parse_json_object as _safe_parse_json_object,
    truncate_emotion_reason as _truncate_emotion_reason,
    truncate_preview as _truncate_preview,
)
from .ffmpeg_locator import FFMPEG_PROBE_TIMEOUT_SECONDS
from .token_risk import (
    TOKEN_RISK_CRITICAL_TOKENS_DEFAULT,
    TOKEN_RISK_HIGH_TOKENS_DEFAULT,
    TOKEN_RISK_MEDIUM_TOKENS_DEFAULT,
    TokenRiskAssessment,
    TokenRiskPolicy,
    compact_text_for_prompt as _compact_text_for_prompt,
    estimate_text_tokens as _estimate_text_tokens,
)

try:
    on_agent_begin = filter.on_agent_begin
except AttributeError:

    def on_agent_begin(*args, **kwargs):
        return lambda func: func


try:
    from astrbot.core.star.star import StarMetadata

    if not hasattr(StarMetadata, "pages"):
        StarMetadata.pages = []
except Exception:
    pass

try:
    from astrbot.core.provider.entities import ProviderRequest as CoreProviderRequest
except Exception:
    CoreProviderRequest = ProviderRequest


VOLC_FLASH_ENDPOINT = (
    "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
)
VOLC_RESOURCE_ID = "volc.bigasr.auc_turbo"
VOLC_SUCCESS_CODE = "20000000"
VOLC_SILENT_AUDIO_CODE = "20000003"
PLUGIN_VERSION = "3.0.0-pr1"
PLUGIN_NAME = "astrbot_plugin_volcengine_asr"
PLUGIN_REPO_URL = "https://github.com/Ayleovelle/astrbot_plugin_volcengine_asr"
SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".opus"}
TRANSCODE_HINT_EXTS = {".amr", ".silk", ".slk", ".m4a", ".aac", ".flac", ".webm"}
INLINE_AUDIO_REF_PATTERN = re.compile(
    r"(?:base64://|(?:^|[\s\[\(\{\"'=:,;<>])"
    r"(?:https?://[^\s\]\)\}\"'<>]+|[A-Za-z]:[\\/][^\s\]\)\}\"'<>]+|(?:\.{1,2}[\\/]|/)[^\s\]\)\}\"'<>]+|[\w.-]+)"
    r"\.(?:wav|mp3|ogg|opus|amr|silk|slk|m4a|aac|flac|webm)"
    r"(?:[?#][^\s\]\)\}\"'<>]*)?"
    r"(?=$|[\s\]\)\}\"'<>，。！？、,;:]))",
    re.IGNORECASE,
)
PROVIDER_REQUEST_CACHE_KEYS = {"provider_request", "request", "req", "llm_request"}
AUDIO_REFERENCE_KEYS = {
    "audio",
    "audio_url",
    "audio_urls",
    "audios",
    "base64",
    "file",
    "file_id",
    "file_ids",
    "file_name",
    "file_url",
    "file_urls",
    "filename",
    "files",
    "path",
    "record",
    "records",
    "url",
    "urls",
}
CACHE_CONTENT_ATTRS = (
    "attachments",
    "audios",
    "cache",
    "cache_content",
    "cached_content",
    "cached_messages",
    "content",
    "context",
    "contexts",
    "conversation",
    "data",
    "extra_user_content_parts",
    "files",
    "history",
    "input",
    "input_messages",
    "media",
    "message",
    "message_chain",
    "messages",
    "metadata",
    "original_message",
    "payload",
    "raw_content",
    "raw_message",
    "request",
    "segments",
    "session",
    "stage_data",
    "tools",
)
DEFAULT_VOICE_PROMPT_TEMPLATE = (
    "<text>[符号前面的内容是用户的语音转文字内容，请通过上述内容判断用户情绪，"
    "并且尽量使用语音回复，严禁讨论本插件的实际功能“转文字”的事实，回复时不要考虑括号内内容]"
)
DEFAULT_UNCLEAR_VOICE_PROMPT = (
    "[用户刚刚发送了一条语音，但系统没有听清内容（可能是静音、杂音或识别失败）。"
    "请以没听清为由，自然地请用户再说一次或改用文字补充，不要直接说是系统错误。]"
)
DEFAULT_UNCLEAR_MEMORY_TEXT = "用户发送了一条语音，但未识别出有效内容。"
ASR_EXTRA_TEXT = "volcengine_asr_text"
ASR_EXTRA_MEMORY_TEXT = "volcengine_asr_memory_text"
ASR_EXTRA_LLM_TEXT = "volcengine_asr_llm_text"
ASR_EXTRA_INJECTED = "volcengine_asr_injected"
ASR_EXTRA_UNCLEAR = "volcengine_asr_unclear"
ASR_EXTRA_EMOTION_RESULT = "volcengine_asr_emotion_result"
ASR_EXTRA_EMOTION_APPLIED = "volcengine_asr_emotion_applied"
ASR_EXTRA_EMOTION_INTERNAL_CALL = "volcengine_asr_emotion_internal_call"
ASR_EXTRA_DIAGNOSTICS = "volcengine_asr_diagnostics"
ASR_EXTRA_TOKEN_RISK = "volcengine_asr_token_risk"
WEBUI_CONFIG_SCHEMA_PATH = Path(__file__).resolve().with_name("_conf_schema.json")
WEBUI_EMOTION_HISTORY_LIMIT_MIN = 100
WEBUI_EMOTION_HISTORY_LIMIT_MAX = 200
WEBUI_DEFAULT_EMOTION_HISTORY_LIMIT = 160
EMOTION_CONTEXT_CHAR_LIMIT_DEFAULT = 2000
WEBUI_CONFIG_KEYS = (
    "api_key",
    "app_key",
    "access_key",
    "resource_id",
    "endpoint",
    "uid",
    "submit_mode",
    "max_audio_mb",
    "timeout_seconds",
    "enable_transcode",
    "prefer_bundled_ffmpeg",
    "ffmpeg_path",
    "transcode_output_format",
    "transcode_sample_rate",
    "transcode_channels",
    "auto_recognize",
    "enable_private",
    "enable_group",
    "only_when_at_or_wake",
    "ignore_self",
    "inject_as_user_input",
    "stop_event_after_recognition",
    "send_empty_result_message",
    "reply_transcription",
    "reply_template",
    "voice_prompt_template",
    "inject_on_unclear_voice",
    "unclear_voice_prompt",
    "enable_emotion_analysis",
    "emotion_model_id",
    "emotion_context_turns",
    "emotion_context_char_limit",
    "emotion_max_respect_weight_percent",
    "emotion_timeout_seconds",
    "emotion_fail_open",
    "emotion_prompt_template",
    "enable_token_risk_guard",
    "token_risk_medium_tokens",
    "token_risk_high_tokens",
    "token_risk_critical_tokens",
    "show_logid",
    "notify_config_error",
    "notify_asr_error",
    "enable_itn",
    "enable_punc",
    "enable_ddc",
    "enable_speaker_info",
    "webui_emotion_history_limit",
)
WEBUI_SECRET_CONFIG_KEYS = {"api_key", "access_key"}
WEBUI_CLIENT_CONFIG_KEYS = {
    "api_key",
    "app_key",
    "access_key",
    "resource_id",
    "endpoint",
    "uid",
    "timeout_seconds",
    "enable_itn",
    "enable_punc",
    "enable_ddc",
    "enable_speaker_info",
}
WEBUI_INT_RANGES = {
    "max_audio_mb": (1, 100),
    "timeout_seconds": (5, 300),
    "transcode_sample_rate": (8000, 48000),
    "transcode_channels": (1, 2),
    "emotion_context_turns": (0, 20),
    "emotion_context_char_limit": (0, 20000),
    "emotion_max_respect_weight_percent": (0, 100),
    "emotion_timeout_seconds": (1, 120),
    "token_risk_medium_tokens": (1000, 500000),
    "token_risk_high_tokens": (1000, 500000),
    "token_risk_critical_tokens": (1000, 500000),
    "webui_emotion_history_limit": (
        WEBUI_EMOTION_HISTORY_LIMIT_MIN,
        WEBUI_EMOTION_HISTORY_LIMIT_MAX,
    ),
}


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


@dataclass(slots=True)
class RecognitionBatch:
    results: list[AsrResult]
    errors: list[str]
    unclear_count: int = 0
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class VoiceInput:
    index: int
    record: Any
    sources: list[str]
    event: AstrMessageEvent | None = None

    def to_diagnostic(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "sources": self.sources,
        }


@dataclass(slots=True)
class AudioPayloadResult:
    payload: dict[str, str]
    source: str
    source_type: str
    input_suffix: str = ""
    detected_suffix: str = ""
    input_bytes: int | None = None
    output_format: str = ""
    output_bytes: int | None = None
    transcoded: bool = False

    def to_diagnostic(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "input_suffix": self.input_suffix,
            "detected_suffix": self.detected_suffix,
            "input_bytes": self.input_bytes,
            "output_format": self.output_format,
            "output_bytes": self.output_bytes,
            "transcoded": self.transcoded,
            "submit_mode": "url" if "url" in self.payload else "base64",
        }


@dataclass(slots=True)
class VoiceInjectionPlan:
    memory_text: str
    llm_text: str
    raw_text: str
    unclear: bool = False
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def apply_to_event(self, event: AstrMessageEvent) -> None:
        _replace_event_message_with_plain_text(event, self.memory_text)
        _sanitize_event_cached_content(event, self.memory_text)
        extras = {
            ASR_EXTRA_TEXT: self.raw_text or self.memory_text,
            ASR_EXTRA_MEMORY_TEXT: self.memory_text,
            ASR_EXTRA_LLM_TEXT: self.llm_text,
            ASR_EXTRA_INJECTED: True,
            ASR_EXTRA_UNCLEAR: self.unclear,
        }
        if self.diagnostics:
            extras[ASR_EXTRA_DIAGNOSTICS] = self.diagnostics
        _set_event_extras(event, extras)


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
    record_cls = getattr(Comp, "Record", None)
    if record_cls is not None and isinstance(component, record_cls):
        return True
    if isinstance(component, dict):
        component_type = component.get("type", "")
        type_value = getattr(component_type, "value", component_type)
        return str(type_value).lower() == "record"
    component_type = getattr(component, "type", "")
    type_value = getattr(component_type, "value", component_type)
    if str(type_value).lower() == "record":
        return True

    if component.__class__.__name__.lower() != "record":
        return False
    for attr in ("base64", "path", "file", "file_id", "url", "data"):
        if getattr(component, attr, None):
            return True
    return False


def _base64_payload_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("base64://"):
        text = text.removeprefix("base64://")
    if "," in text and ";base64" in text.split(",", 1)[0].lower():
        text = text.split(",", 1)[1]
    return re.sub(r"\s+", "", text)


def _normalize_base64_source(value: Any) -> str:
    payload = _base64_payload_text(value)
    return f"base64://{payload}" if payload else ""


def _extract_record_sources(record: Any) -> list[str]:
    sources: list[str] = []

    def append_source(value: Any) -> None:
        if value:
            source = str(value).strip()
            if source and source not in sources:
                sources.append(source)

    def append_from_mapping(data: dict[str, Any]) -> None:
        for attr in ("base64", "path", "file", "file_id", "url", "audio_url", "file_url"):
            value = data.get(attr)
            if attr == "base64" and value:
                value = _normalize_base64_source(value)
            append_source(value)

    if isinstance(record, dict):
        append_from_mapping(record)
        data = record.get("data")
        if isinstance(data, dict):
            append_from_mapping(data)
        return sources

    for attr in ("base64", "path", "file", "file_id", "url", "audio_url", "file_url"):
        value = getattr(record, attr, None)
        if attr == "base64" and value:
            value = _normalize_base64_source(value)
        append_source(value)

    data = getattr(record, "data", None)
    if isinstance(data, dict):
        append_from_mapping(data)
    elif data is not None:
        for attr in ("base64", "path", "file", "file_id", "url", "audio_url", "file_url"):
            value = getattr(data, attr, None)
            if attr == "base64" and value:
                value = _normalize_base64_source(value)
            append_source(value)
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
    parsed_path = urlparse(source).path if source.startswith(("http://", "https://", "file://")) else source
    return Path(unquote(parsed_path)).suffix.lower()


def _onebot_record_result_source(result: Any) -> str:
    if not result:
        return ""
    if isinstance(result, str):
        return result.strip()

    def from_mapping(data: dict[str, Any]) -> str:
        for key in ("base64", "url", "file", "path"):
            value = data.get(key)
            if value:
                if key == "base64":
                    return _normalize_base64_source(value)
                return str(value).strip()
        return ""

    if isinstance(result, dict):
        data = result.get("data")
        if isinstance(data, dict):
            nested = from_mapping(data)
            if nested:
                return nested
        return from_mapping(result)

    for attr in ("base64", "url", "file", "path"):
        value = getattr(result, attr, None)
        if value:
            if attr == "base64":
                return _normalize_base64_source(value)
            return str(value).strip()
    return ""


def _detect_audio_suffix(data: bytes, source: str = "") -> str:
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return ".wav"
    if data.startswith(b"OggS"):
        return ".ogg"
    if len(data) > 2 and data[0] == 0xFF and (data[1] & 0xF0) == 0xF0:
        return ".aac"
    if data.startswith(b"ID3") or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return ".mp3"
    if data.startswith(b"#!AMR"):
        return ".amr"
    if data.startswith(b"#!SILK"):
        return ".silk"
    if data.startswith(b"fLaC"):
        return ".flac"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brands = data[8:32].lower()
        if b"m4a" in brands or b"mp42" in brands or b"isom" in brands:
            return ".m4a"
    return _source_suffix(source)


def _estimate_base64_size(base64_text: str) -> int:
    cleaned = _base64_payload_text(base64_text)
    if not cleaned:
        return 0
    padding = cleaned[-2:].count("=")
    return max(0, (len(cleaned) * 3 // 4) - padding)


def _max_mb_text(max_bytes: int) -> int:
    return max_bytes // 1024 // 1024


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_with_fallback(template: str, values: dict[str, Any]) -> str:
    try:
        return template.format(**values)
    except (KeyError, ValueError, IndexError):
        return str(values.get("text", ""))


def _render_prompt_template(template: str, values: dict[str, Any]) -> str:
    template = template.replace("<text>", "{text}")
    return _format_with_fallback(template, values).strip()


def _replace_first_text(text: str, old: str, new: str) -> tuple[str, bool]:
    if not old or old not in text:
        return text, False
    return text.replace(old, new, 1), True


def _plain_message_chain(text: str) -> list[Any]:
    return [Comp.Plain(text)]


def _looks_like_message_chain(value: Any) -> bool:
    if isinstance(value, list):
        return True
    if isinstance(value, (str, bytes, bytearray, dict)) or value is None:
        return False
    if _is_record_component(value):
        return False
    return any(hasattr(value, attr) for attr in ("chain", "message", "message_chain")) or (
        value.__class__.__name__.lower() in {"messagechain", "messagechainobj"}
    )


def _message_chain_items(chain: Any) -> list[Any]:
    if isinstance(chain, list):
        return list(chain)
    if isinstance(chain, (str, bytes, bytearray, dict)) or chain is None:
        return []
    for attr in ("chain", "message", "message_chain"):
        value = getattr(chain, attr, None)
        if isinstance(value, list):
            return list(value)
    try:
        return list(chain)
    except TypeError:
        return []


def _iter_message_chains(event: AstrMessageEvent, *, include_extra_caches: bool = True) -> list[Any]:
    chains: list[Any] = []
    seen: set[int] = set()
    visited: set[int] = set()

    def append_chain(chain: Any, depth: int = 0) -> None:
        if chain is None or depth > 8:
            return
        chain_id = id(chain)
        if (isinstance(chain, dict) or _looks_like_message_chain(chain)) and chain_id in visited:
            return
        if isinstance(chain, dict) or _looks_like_message_chain(chain):
            visited.add(chain_id)

        if _looks_like_message_chain(chain):
            if chain_id not in seen:
                seen.add(chain_id)
                chains.append(chain)
            items = _message_chain_items(chain)
            for attr in ("chain", "message", "message_chain"):
                value = getattr(chain, attr, None)
                if isinstance(value, list):
                    append_chain(value, depth + 1)
            for item in items:
                if isinstance(item, (list, dict)) or _is_record_component(item):
                    append_chain(item, depth + 1)
                else:
                    for attr in ("chain", "message", "message_chain", "raw_message", "content"):
                        if hasattr(item, attr):
                            append_chain(getattr(item, attr), depth + 1)
        elif _is_record_component(chain):
            if chain_id not in seen:
                seen.add(chain_id)
                chains.append([chain])
        elif isinstance(chain, dict):
            preferred_keys = (
                "message",
                "message_chain",
                "raw_message",
                "data",
                "segments",
                "original_message",
                "content",
            )
            for key in preferred_keys:
                if key in chain:
                    append_chain(chain.get(key), depth + 1)
            for key, value in chain.items():
                if key in preferred_keys:
                    continue
                if isinstance(value, (list, dict)) or _is_record_component(value):
                    append_chain(value, depth + 1)

    message_obj = getattr(event, "message_obj", None)
    if message_obj is not None:
        append_chain(getattr(message_obj, "message", None))
        append_chain(getattr(message_obj, "message_chain", None))
        append_chain(getattr(message_obj, "raw_message", None))
        if include_extra_caches:
            for attr in ("extras", "_extras", "extra"):
                extra_container = getattr(message_obj, attr, None)
                if isinstance(extra_container, dict):
                    append_chain(extra_container, 1)

    append_chain(getattr(event, "message", None))
    append_chain(getattr(event, "message_chain", None))
    append_chain(getattr(event, "raw_message", None))
    if include_extra_caches:
        for attr in ("extras", "_extras", "extra"):
            extra_container = getattr(event, attr, None)
            if isinstance(extra_container, dict):
                append_chain(extra_container, 1)

    get_messages = getattr(event, "get_messages", None)
    if callable(get_messages):
        try:
            append_chain(get_messages())
        except Exception as exc:
            logger.warning(f"读取事件消息链失败，已跳过该来源：{exc}")

    return chains


def _mutate_message_chains_to_plain_text(event: AstrMessageEvent, text: str) -> None:
    for old_chain in _iter_message_chains(event, include_extra_caches=False):
        replacement = _plain_message_chain(text)
        for attr in ("chain", "message", "message_chain"):
            nested_chain = getattr(old_chain, attr, None)
            if isinstance(nested_chain, list):
                nested_chain[:] = replacement
        try:
            old_chain[:] = replacement
            continue
        except Exception as exc:
            logger.warning(f"原地清理旧语音消息链切片失败，已尝试清理内部链：{exc}")


def _ensure_event_get_message_str_returns_voice_text(event: AstrMessageEvent, text: str) -> None:
    try:
        setattr(event, "_volcengine_asr_message_text", text)
    except Exception:
        pass
    try:
        if getattr(event, "_volcengine_asr_get_message_str_guarded", False):
            return
    except Exception:
        return

    original_getter = getattr(event, "get_message_str", None)
    if not callable(original_getter):
        original_getter = None

    def get_message_str() -> str:
        get_extra = getattr(event, "get_extra", None)
        if callable(get_extra):
            for key in (ASR_EXTRA_MEMORY_TEXT, ASR_EXTRA_TEXT):
                try:
                    value = get_extra(key, "")
                except Exception:
                    value = ""
                if isinstance(value, str) and value.strip():
                    return value.strip()

        message_obj = getattr(event, "message_obj", None)
        candidates = (
            getattr(event, "message_str", ""),
            getattr(message_obj, "message_str", "") if message_obj is not None else "",
            getattr(event, "_volcengine_asr_message_text", ""),
        )
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip()

        if original_getter is not None:
            try:
                value = original_getter()
            except Exception:
                value = ""
            if isinstance(value, str):
                return value.strip()
        return ""

    try:
        setattr(event, "_volcengine_asr_original_get_message_str", original_getter)
        setattr(event, "get_message_str", get_message_str)
        setattr(event, "_volcengine_asr_get_message_str_guarded", True)
    except Exception as exc:
        logger.debug(f"安装语音转写文本读取保护失败，已跳过：{exc}")


def _replace_event_message_with_plain_text(event: AstrMessageEvent, text: str) -> None:
    chain = _plain_message_chain(text)
    _mutate_message_chains_to_plain_text(event, text)
    event.message_str = text
    _ensure_event_get_message_str_returns_voice_text(event, text)

    for attr in ("message", "message_chain"):
        if hasattr(event, attr):
            setattr(event, attr, chain.copy())
    if hasattr(event, "raw_message"):
        setattr(event, "raw_message", text)

    message_obj = getattr(event, "message_obj", None)
    if message_obj is not None:
        setattr(message_obj, "message_str", text)
        setattr(message_obj, "message", chain.copy())
        if hasattr(message_obj, "message_chain"):
            setattr(message_obj, "message_chain", chain.copy())
        if hasattr(message_obj, "raw_message"):
            setattr(message_obj, "raw_message", text)


def _looks_like_audio_reference(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    if not text:
        return False
    audio_exts = SUPPORTED_AUDIO_EXTS | TRANSCODE_HINT_EXTS
    if text.startswith("base64://"):
        return True
    parsed_path = urlparse(text).path if text.startswith(("http://", "https://")) else text
    parsed_path = unquote(parsed_path)
    if any(parsed_path.endswith(ext) for ext in audio_exts):
        return True
    return any(f"{ext}]" in text or f"{ext})" in text for ext in audio_exts)


def _contains_inline_audio_reference(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    return _looks_like_audio_reference(text) or INLINE_AUDIO_REF_PATTERN.search(text) is not None


def _mapping_has_voice_semantics(mapping: dict[Any, Any]) -> bool:
    marker_keys = {"audio", "audio_url", "audio_urls", "audios", "record", "records"}
    type_value = _content_type(mapping)
    if type_value in {"audio", "audio_url", "input_audio", "file", "record"}:
        return True
    return any(str(key).lower() in marker_keys for key in mapping)


def _content_type(value: Any) -> str:
    value_type = value.get("type", "") if isinstance(value, dict) else getattr(value, "type", "")
    type_value = getattr(value_type, "value", value_type)
    return str(type_value).strip().lower()


def _object_to_sanitizable_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, (dict, list, str, bytes, bytearray)) or value is None:
        return None

    dumped = None
    for method_name in ("model_dump", "dict"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                dumped = method()
            except Exception:
                dumped = None
            if isinstance(dumped, dict):
                return dumped

    data: dict[str, Any] = {}
    for attr in (
        "type",
        "text",
        "content",
        "message",
        "message_chain",
        "raw_message",
        "audio_url",
        "audio_urls",
        "url",
        "file",
        "path",
        "data",
    ):
        if hasattr(value, attr):
            data[attr] = getattr(value, attr)
    return data or None


def _sanitize_content_value(value: Any, fallback_text: str, llm_text: str | None = None) -> Any:
    request_text = llm_text if isinstance(llm_text, str) and llm_text.strip() else fallback_text
    if isinstance(value, list):
        cleaned = []
        for item in value:
            item_cleaned = _sanitize_content_value(item, fallback_text, request_text)
            if item_cleaned is not None:
                cleaned.append(item_cleaned)
        return cleaned

    if isinstance(value, dict):
        value_type = _content_type(value)
        if value_type in {"audio", "audio_url", "input_audio", "file", "record"}:
            return None
        if _is_record_component(value):
            return None

        cleaned: dict[Any, Any] = {}
        has_voice_semantics = _mapping_has_voice_semantics(value)
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in AUDIO_REFERENCE_KEYS and (
                _contains_sanitizable_voice_reference(item)
                or (has_voice_semantics and key_text in {"file_id", "file_ids", "file_name", "filename"})
            ):
                cleaned[key] = []
                continue
            if key_text in {
                "message",
                "message_chain",
                "raw_message",
            }:
                if _contains_sanitizable_voice_reference(item):
                    cleaned[key] = fallback_text if key_text == "raw_message" else _plain_message_chain(fallback_text)
                else:
                    item_cleaned = _sanitize_content_value(item, fallback_text, request_text)
                    if item_cleaned is not None:
                        cleaned[key] = item_cleaned
                continue
            item_cleaned = _sanitize_content_value(item, fallback_text, request_text)
            if item_cleaned is not None:
                cleaned[key] = item_cleaned
        if cleaned.get("type") == "text" and not str(cleaned.get("text", "")).strip():
            return None
        if not cleaned and value_type:
            return None
        return cleaned

    if _is_record_component(value):
        return None
    if _looks_like_provider_request(value):
        _sanitize_provider_request(value, fallback_text, request_text)
        return value
    object_dict = _object_to_sanitizable_dict(value)
    if object_dict is not None:
        return _sanitize_content_value(object_dict, fallback_text, request_text)
    if _looks_like_audio_reference(value):
        return None
    if _contains_inline_audio_reference(value):
        return request_text
    return value


def _sanitize_content_parts(parts: Any, fallback_text: str, llm_text: str | None = None) -> list[Any]:
    if not isinstance(parts, list):
        return []
    request_text = llm_text if isinstance(llm_text, str) and llm_text.strip() else fallback_text
    cleaned = []
    for part in parts:
        part_dict = _object_to_sanitizable_dict(part)
        if part_dict is not None:
            if not _contains_sanitizable_voice_reference(part_dict):
                cleaned.append(part)
                continue
            sanitized = _sanitize_content_value(part_dict, fallback_text, request_text)
            if (
                isinstance(sanitized, dict)
                and _content_type(sanitized) == "text"
                and hasattr(part, "text")
                and "text" in sanitized
            ):
                try:
                    setattr(part, "text", sanitized["text"])
                    cleaned.append(part)
                    continue
                except Exception:
                    pass
        else:
            sanitized = _sanitize_content_value(part, fallback_text, request_text)
        if sanitized is not None:
            cleaned.append(sanitized)
    return cleaned


def _contains_sanitizable_voice_reference(value: Any, depth: int = 0) -> bool:
    if value is None or depth > 8:
        return False
    if _is_record_component(value) or _looks_like_audio_reference(value) or _contains_inline_audio_reference(value):
        return True
    if _looks_like_provider_request(value) or _is_event_like(value):
        return False
    if isinstance(value, list):
        return any(_contains_sanitizable_voice_reference(item, depth + 1) for item in value)
    if isinstance(value, dict):
        value_type = _content_type(value)
        if value_type in {"audio", "audio_url", "input_audio", "file", "record"}:
            return True
        has_voice_semantics = _mapping_has_voice_semantics(value)
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in PROVIDER_REQUEST_CACHE_KEYS and _looks_like_provider_request(item):
                return True
            if _looks_like_provider_request(item):
                return True
            if key_text in AUDIO_REFERENCE_KEYS and (
                _contains_sanitizable_voice_reference(item, depth + 1)
                or (has_voice_semantics and key_text in {"file_id", "file_ids", "file_name", "filename"})
            ):
                return True
            if _contains_sanitizable_voice_reference(item, depth + 1):
                return True
        return False
    object_dict = _object_to_sanitizable_dict(value)
    if object_dict is not None:
        return _contains_sanitizable_voice_reference(object_dict, depth + 1)
    return False


def _sanitize_provider_request(req: ProviderRequest, memory_text: str, llm_text: str) -> None:
    try:
        if hasattr(req, "audio_urls"):
            req.audio_urls = []
    except Exception:
        pass

    for attr in CACHE_CONTENT_ATTRS:
        try:
            value = getattr(req, attr, None)
        except Exception:
            continue
        replacement_set = False
        replacement = None
        if isinstance(value, list):
            replacement = _sanitize_content_parts(value, memory_text, llm_text)
            replacement_set = True
        elif isinstance(value, dict):
            replacement = _sanitize_content_value(value, memory_text, llm_text)
            replacement_set = True
        elif _contains_sanitizable_voice_reference(value):
            replacement = _sanitize_content_value(value, memory_text, llm_text)
            replacement_set = True
        elif _looks_like_audio_reference(value) or _is_record_component(value):
            replacement = None
            replacement_set = True
        if replacement_set:
            try:
                setattr(req, attr, replacement)
            except Exception:
                continue

    try:
        prompt = getattr(req, "prompt", None)
    except Exception:
        return
    if isinstance(prompt, str) and _contains_inline_audio_reference(prompt):
        try:
            req.prompt = llm_text
        except Exception:
            pass


def _sanitize_mapping_cache(mapping: dict[Any, Any], memory_text: str, llm_text: str) -> None:
    for key in list(mapping):
        key_text = str(key).lower()
        value = mapping[key]
        if key_text.startswith("volcengine_asr_"):
            continue
        if key_text in PROVIDER_REQUEST_CACHE_KEYS and _looks_like_provider_request(value):
            _sanitize_provider_request(value, memory_text, llm_text)
            continue
        if key_text in PROVIDER_REQUEST_CACHE_KEYS and isinstance(value, dict):
            if not _contains_sanitizable_voice_reference(value):
                continue
            clean_request = _build_clean_provider_request(llm_text)
            mapping[key] = clean_request if clean_request is not None else _sanitize_content_value(value, memory_text, llm_text)
            continue
        if _looks_like_provider_request(value):
            _sanitize_provider_request(value, memory_text, llm_text)
            continue
        if key_text in AUDIO_REFERENCE_KEYS and _contains_sanitizable_voice_reference(value):
            mapping[key] = []
            continue
        if not _contains_sanitizable_voice_reference(value):
            continue
        mapping[key] = _sanitize_content_value(value, memory_text, llm_text)


def _set_sanitized_attr(owner: Any, attr: str, fallback_text: str, llm_text: str | None = None) -> None:
    request_text = llm_text if isinstance(llm_text, str) and llm_text.strip() else fallback_text
    try:
        value = getattr(owner, attr)
    except Exception:
        return
    if _is_event_like(value) or _looks_like_provider_request(value):
        if _looks_like_provider_request(value):
            _sanitize_provider_request(value, fallback_text, request_text)
        return
    if isinstance(value, dict):
        _sanitize_mapping_cache(value, fallback_text, request_text)
        return
    if not _contains_sanitizable_voice_reference(value):
        return
    sanitized = _sanitize_content_value(value, fallback_text, request_text)
    try:
        setattr(owner, attr, sanitized)
    except Exception:
        return


def _is_event_like(value: Any) -> bool:
    return value is not None and hasattr(value, "get_extra") and hasattr(value, "set_extra")


def _sanitize_visible_object_caches(owner: Any, fallback_text: str, llm_text: str | None = None) -> None:
    request_text = llm_text if isinstance(llm_text, str) and llm_text.strip() else fallback_text
    if owner is None or isinstance(owner, (str, bytes, bytearray, dict, list)) or _is_event_like(owner):
        return
    for attr in CACHE_CONTENT_ATTRS:
        if hasattr(owner, attr):
            _set_sanitized_attr(owner, attr, fallback_text, request_text)


def _sanitize_event_cached_content(event: AstrMessageEvent, text: str, llm_text: str | None = None) -> None:
    request_text = llm_text if isinstance(llm_text, str) and llm_text.strip() else text
    containers = []
    seen_containers: set[int] = set()
    for owner in (event, getattr(event, "message_obj", None)):
        if owner is None:
            continue
        for attr in ("extras", "_extras", "extra"):
            container = getattr(owner, attr, None)
            if isinstance(container, dict) and id(container) not in seen_containers:
                seen_containers.add(id(container))
                containers.append(container)

    for container in containers:
        _sanitize_mapping_cache(container, text, request_text)


def _sanitize_run_context_cached_content(run_context: Any, memory_text: str, llm_text: str) -> None:
    if run_context is None:
        return
    if isinstance(run_context, dict):
        _sanitize_mapping_cache(run_context, memory_text, llm_text)
        return
    _sanitize_visible_object_caches(run_context, memory_text, llm_text)
    if _looks_like_provider_request(run_context):
        _sanitize_provider_request(run_context, memory_text, llm_text)
    for attr in ("provider_request", "request", "req", "llm_request"):
        try:
            value = getattr(run_context, attr)
        except Exception:
            continue
        if _looks_like_provider_request(value):
            _sanitize_provider_request(value, memory_text, llm_text)
        elif isinstance(value, dict):
            _sanitize_mapping_cache(value, memory_text, llm_text)
        elif value is not run_context:
            _sanitize_visible_object_caches(value, memory_text, llm_text)


def _set_event_extras(event: AstrMessageEvent, extras: dict[str, Any]) -> None:
    for key, value in extras.items():
        event.set_extra(key, value)


def _set_clean_provider_request(event: AstrMessageEvent, prompt: str) -> None:
    req = _build_clean_provider_request(prompt)
    if req is not None:
        event.set_extra("provider_request", req)


def _get_event_provider_request(event: AstrMessageEvent) -> Any | None:
    for key in ("provider_request", "request", "req", "llm_request"):
        try:
            value = event.get_extra(key, None)
        except Exception:
            continue
        if _looks_like_provider_request(value):
            return value
    return None


def _resolve_provider_request_argument(
    event: AstrMessageEvent,
    req: Any | None = None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
) -> Any | None:
    if _looks_like_provider_request(req):
        return req
    for value in args:
        if _looks_like_provider_request(value):
            return value
    for key in ("req", "request", "provider_request", "llm_request"):
        value = (kwargs or {}).get(key)
        if _looks_like_provider_request(value):
            return value
    for value in (kwargs or {}).values():
        if _looks_like_provider_request(value):
            return value
    return _get_event_provider_request(event)


def _ensure_clean_voice_event_for_agent(event: AstrMessageEvent, run_context: Any | None = None) -> None:
    memory_text = event.get_extra(ASR_EXTRA_MEMORY_TEXT, "")
    llm_text = event.get_extra(ASR_EXTRA_LLM_TEXT, "")
    if not isinstance(memory_text, str) or not memory_text.strip():
        return
    memory_text = memory_text.strip()
    llm_text = llm_text.strip() if isinstance(llm_text, str) and llm_text.strip() else memory_text
    _replace_event_message_with_plain_text(event, memory_text)
    _sanitize_event_cached_content(event, memory_text, llm_text)
    req = _get_event_provider_request(event)
    if _looks_like_provider_request(req):
        _sanitize_provider_request(req, memory_text, llm_text)
    _sanitize_run_context_cached_content(run_context, memory_text, llm_text)


def _build_clean_provider_request(prompt: str) -> Any | None:
    try:
        req = CoreProviderRequest()
    except Exception as exc:
        logger.warning(f"创建干净 ProviderRequest 失败，将回退到事件文本注入：{exc}")
        return None
    req.prompt = prompt
    req.image_urls = []
    req.audio_urls = []
    req.extra_user_content_parts = []
    return req


def _looks_like_provider_request(value: Any) -> bool:
    if value is None or isinstance(value, (dict, list, str, bytes, bytearray)):
        return False
    if hasattr(value, "prompt"):
        return True
    if callable(getattr(value, "model_dump_for_context", None)):
        return True
    class_name = value.__class__.__name__.lower()
    module_name = getattr(value.__class__, "__module__", "").lower()
    if "providerrequest" in class_name or ("provider" in module_name and "request" in class_name):
        return True
    return False


def _disable_default_llm_reentry(event: AstrMessageEvent) -> None:
    should_call_llm = getattr(event, "should_call_llm", None)
    if callable(should_call_llm):
        try:
            should_call_llm(True)
            return
        except Exception as exc:
            logger.warning(f"禁用默认 LLM 重入失败，将回退到直接设置 call_llm：{exc}")
    try:
        setattr(event, "call_llm", True)
    except Exception as exc:
        logger.warning(f"设置 call_llm 标记失败：{exc}")


def _stop_voice_event_with_plain_text(
    event: AstrMessageEvent,
    text: str,
    *,
    diagnostics: list[dict[str, Any]] | None = None,
) -> None:
    fallback_text = (text or DEFAULT_UNCLEAR_MEMORY_TEXT).strip() or DEFAULT_UNCLEAR_MEMORY_TEXT
    _replace_event_message_with_plain_text(event, fallback_text)
    _sanitize_event_cached_content(event, fallback_text)
    extras = {
        ASR_EXTRA_TEXT: fallback_text,
        ASR_EXTRA_MEMORY_TEXT: fallback_text,
        ASR_EXTRA_LLM_TEXT: fallback_text,
        ASR_EXTRA_INJECTED: False,
        ASR_EXTRA_UNCLEAR: fallback_text == DEFAULT_UNCLEAR_MEMORY_TEXT,
    }
    if diagnostics:
        extras[ASR_EXTRA_DIAGNOSTICS] = diagnostics
    _set_event_extras(event, extras)
    event.stop_event()


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"读取 JSON 文件失败：{path}，error={exc}")
        return {}
    return value if isinstance(value, dict) else {}


def _mask_secret(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}...{text[-4:]}"


def _is_unchanged_masked_secret(value: Any, current_value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return text == "****" or text == _mask_secret(current_value)


def _coerce_webui_config_value(key: str, value: Any, schema: dict[str, Any]) -> tuple[bool, Any, str]:
    field = schema.get(key) or {}
    value_type = field.get("type")
    options = field.get("options")
    if value_type == "bool":
        if isinstance(value, bool):
            coerced = value
        elif isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "y", "启用"}:
                coerced = True
            elif normalized in {"0", "false", "no", "off", "n", "关闭"}:
                coerced = False
            else:
                return False, None, f"{key} 必须是布尔值"
        else:
            return False, None, f"{key} 必须是布尔值"
    elif value_type == "int":
        coerced = _safe_int(value)
        if coerced is None:
            return False, None, f"{key} 必须是整数"
        minimum, maximum = WEBUI_INT_RANGES.get(key, (None, None))
        if minimum is not None and coerced < minimum:
            return False, None, f"{key} 不能小于 {minimum}"
        if maximum is not None and coerced > maximum:
            return False, None, f"{key} 不能大于 {maximum}"
    elif value_type == "string":
        coerced = "" if value is None else str(value).strip()
        if options and all(isinstance(option, str) for option in options):
            normalized = coerced.lower()
            if normalized in options:
                coerced = normalized
    else:
        coerced = value

    if options and coerced not in options:
        return False, None, f"{key} 必须是以下值之一：{', '.join(map(str, options))}"
    return True, coerced, ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _event_identity(event: AstrMessageEvent) -> dict[str, str]:
    message_obj = getattr(event, "message_obj", None)
    sender = getattr(message_obj, "sender", None) if message_obj is not None else None
    sender_id = getattr(sender, "user_id", "") if sender is not None else ""
    if not sender_id:
        get_sender_id = getattr(event, "get_sender_id", None)
        if callable(get_sender_id):
            try:
                sender_id = get_sender_id()
            except Exception:
                sender_id = ""
    return {
        "session_id": str(getattr(event, "unified_msg_origin", "") or ""),
        "sender_id": str(sender_id or ""),
        "group_id": str(getattr(message_obj, "group_id", "") or "") if message_obj is not None else "",
    }


def _build_emotion_history_record(
    event: AstrMessageEvent,
    judgement: EmotionJudgement,
    transcription_text: str,
) -> EmotionHistoryRecord:
    identity = _event_identity(event)
    return EmotionHistoryRecord(
        id=str(uuid.uuid4()),
        timestamp=_utc_now_iso(),
        label=judgement.label,
        emotion_weights=dict(judgement.emotion_weights),
        confidence=judgement.confidence,
        respect_weight=judgement.respect_weight,
        valence=judgement.valence,
        arousal=judgement.arousal,
        voice_text_support=judgement.voice_text_support,
        context_support=judgement.context_support,
        reason=judgement.reason,
        text_preview=_truncate_preview(transcription_text),
        text_length=len(transcription_text or ""),
        **identity,
    )


def _parse_ffmpeg_version_output(output: str) -> str | None:
    return _ffmpeg_locator.parse_ffmpeg_version_output(output)


def _probe_ffmpeg_startup(ffmpeg_path: str) -> tuple[bool, str]:
    return _ffmpeg_locator.probe_ffmpeg_startup(ffmpeg_path)


def _append_ffmpeg_candidate(candidates: list[tuple[str, str]], path: str | Path | None, source: str) -> None:
    _ffmpeg_locator.append_ffmpeg_candidate(candidates, path, source)


def _ffmpeg_executable_names() -> list[str]:
    return _ffmpeg_locator.ffmpeg_executable_names()


def _iter_env_ffmpeg_candidates() -> list[tuple[str, str]]:
    return _ffmpeg_locator.iter_env_ffmpeg_candidates()


def _iter_plugin_ffmpeg_candidates() -> list[tuple[str, str]]:
    return _ffmpeg_locator.iter_plugin_ffmpeg_candidates()


def _iter_path_ffmpeg_candidates() -> list[tuple[str, str]]:
    return _ffmpeg_locator.iter_path_ffmpeg_candidates()


def _iter_common_ffmpeg_candidates() -> list[tuple[str, str]]:
    return _ffmpeg_locator.iter_common_ffmpeg_candidates()


def _build_ffmpeg_candidates(configured_path: str, prefer_bundled: bool) -> list[tuple[str, str]]:
    return _ffmpeg_locator.build_ffmpeg_candidates(configured_path, prefer_bundled)


def _select_probeable_ffmpeg(candidates: list[tuple[str, str]]) -> tuple[str, str, str]:
    return _ffmpeg_locator.select_probeable_ffmpeg(candidates, probe=_probe_ffmpeg_startup)


def _resolve_ffmpeg_path(configured_path: str, prefer_bundled: bool) -> tuple[str, str, str]:
    configured_path = (configured_path or "auto").strip()
    return _select_probeable_ffmpeg(_build_ffmpeg_candidates(configured_path, prefer_bundled))


def _get_plugin_bundled_ffmpeg() -> tuple[str, str] | None:
    return _ffmpeg_locator.get_plugin_bundled_ffmpeg()


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
        aclose = getattr(self._client, "aclose", None)
        if callable(aclose):
            await aclose()

    def stream(self, method: str, url: str):
        return self._client.stream(method, url)

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
        return text, _safe_int(duration)


class VolcengineAsrPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        super().__init__(context)
        self.config = config
        self.client = VolcBigModelAsrClient(config)
        self._emotion_history: deque[EmotionHistoryRecord] = deque(
            maxlen=WEBUI_DEFAULT_EMOTION_HISTORY_LIMIT
        )
        self.emotion_engine: EmotionAnalyzer = DefaultEmotionEngine()
        self._reload_runtime_config(recreate_client=False)
        self._register_webui_apis()

    def _reload_runtime_config(self, *, recreate_client: bool = True) -> None:
        if recreate_client:
            old_client = self.client
            self.client = VolcBigModelAsrClient(self.config)
            self._close_old_client(old_client)
        self.auto_recognize = _config_bool(self.config, "auto_recognize", True)
        self.enable_private = _config_bool(self.config, "enable_private", True)
        self.enable_group = _config_bool(self.config, "enable_group", True)
        self.only_when_at_or_wake = _config_bool(self.config, "only_when_at_or_wake", False)
        self.ignore_self = _config_bool(self.config, "ignore_self", True)
        self.stop_event_after_recognition = _config_bool(
            self.config,
            "stop_event_after_recognition",
            True,
        )
        self.send_empty_result_message = _config_bool(self.config, "send_empty_result_message", True)
        self.notify_config_error = _config_bool(self.config, "notify_config_error", True)
        self.notify_asr_error = _config_bool(self.config, "notify_asr_error", True)
        self.show_logid = _config_bool(self.config, "show_logid", False)
        self.submit_mode = _config_str(self.config, "submit_mode", "base64").lower()
        self.inject_as_user_input = _config_bool(self.config, "inject_as_user_input", True)
        self.enable_emotion_analysis = _config_bool(self.config, "enable_emotion_analysis", False)
        self.emotion_model_id = _config_str(self.config, "emotion_model_id", "")
        self.emotion_context_turns = max(0, _config_int(self.config, "emotion_context_turns", 4))
        self.emotion_context_char_limit = max(
            0,
            _config_int(self.config, "emotion_context_char_limit", EMOTION_CONTEXT_CHAR_LIMIT_DEFAULT),
        )
        self.emotion_max_respect_weight = _clamp_float(
            _config_int(self.config, "emotion_max_respect_weight_percent", 60) / 100,
        )
        self.emotion_timeout_seconds = max(1, _config_int(self.config, "emotion_timeout_seconds", 20))
        self.emotion_fail_open = _config_bool(self.config, "emotion_fail_open", True)
        self.emotion_prompt_template = _config_str(
            self.config,
            "emotion_prompt_template",
            DEFAULT_EMOTION_PROMPT_TEMPLATE,
        ) or DEFAULT_EMOTION_PROMPT_TEMPLATE
        self.emotion_weighting_policy: EmotionWeightingPolicy = DEFAULT_EMOTION_WEIGHTING_POLICY
        self.token_risk_policy = TokenRiskPolicy(
            enabled=_config_bool(self.config, "enable_token_risk_guard", True),
            medium_tokens=max(
                1,
                _config_int(self.config, "token_risk_medium_tokens", TOKEN_RISK_MEDIUM_TOKENS_DEFAULT),
            ),
            high_tokens=max(
                1,
                _config_int(self.config, "token_risk_high_tokens", TOKEN_RISK_HIGH_TOKENS_DEFAULT),
            ),
            critical_tokens=max(
                1,
                _config_int(self.config, "token_risk_critical_tokens", TOKEN_RISK_CRITICAL_TOKENS_DEFAULT),
            ),
        )
        self.voice_prompt_template = _config_str(
            self.config,
            "voice_prompt_template",
            DEFAULT_VOICE_PROMPT_TEMPLATE,
        ) or DEFAULT_VOICE_PROMPT_TEMPLATE
        self.inject_on_unclear_voice = _config_bool(self.config, "inject_on_unclear_voice", True)
        self.unclear_voice_prompt = _config_str(
            self.config,
            "unclear_voice_prompt",
            DEFAULT_UNCLEAR_VOICE_PROMPT,
        ) or DEFAULT_UNCLEAR_VOICE_PROMPT
        self.reply_transcription = _config_bool(self.config, "reply_transcription", False)
        self.reply_template = _config_str(self.config, "reply_template", "语音转文字：{text}")
        self.max_audio_bytes = max(1, _config_int(self.config, "max_audio_mb", 20)) * 1024 * 1024
        self.enable_transcode = _config_bool(self.config, "enable_transcode", True)
        self.prefer_bundled_ffmpeg = _config_bool(self.config, "prefer_bundled_ffmpeg", True)
        configured_ffmpeg_path = _config_str(self.config, "ffmpeg_path", "auto") or "auto"
        if self.enable_transcode:
            self.ffmpeg_path, self.ffmpeg_source, self.ffmpeg_error = _resolve_ffmpeg_path(
                configured_ffmpeg_path,
                self.prefer_bundled_ffmpeg,
            )
        else:
            self.ffmpeg_path = "ffmpeg" if configured_ffmpeg_path.lower() in {"", "auto"} else configured_ffmpeg_path
            self.ffmpeg_source = "未探测（自动转码关闭）"
            self.ffmpeg_error = ""
        self.transcode_sample_rate = max(8000, _config_int(self.config, "transcode_sample_rate", 16000))
        self.transcode_channels = max(1, _config_int(self.config, "transcode_channels", 1))
        self.transcode_output_format = _config_str(self.config, "transcode_output_format", "wav").lower()
        if self.transcode_output_format not in {"wav", "mp3", "ogg"}:
            self.transcode_output_format = "wav"
        self.webui_emotion_history_limit = max(
            WEBUI_EMOTION_HISTORY_LIMIT_MIN,
            min(
                WEBUI_EMOTION_HISTORY_LIMIT_MAX,
                _config_int(
                    self.config,
                    "webui_emotion_history_limit",
                    WEBUI_DEFAULT_EMOTION_HISTORY_LIMIT,
                ),
            ),
        )
        if getattr(self, "_emotion_history", None) is not None and (
            self._emotion_history.maxlen != self.webui_emotion_history_limit
        ):
            self._emotion_history = deque(
                list(self._emotion_history)[-self.webui_emotion_history_limit :],
                maxlen=self.webui_emotion_history_limit,
            )

    def _register_webui_apis(self) -> None:
        register_web_api = getattr(self.context, "register_web_api", None)
        if not callable(register_web_api):
            logger.info("当前 AstrBot Context 不支持 register_web_api，插件页面 API 将跳过注册。")
            return
        routes = (
            ("state", self.webui_api_state, ["GET"], "火山 ASR Web UI 状态"),
            ("doctor", self.webui_api_doctor, ["GET"], "火山 ASR 诊断报告"),
            ("config", self.webui_api_config, ["GET"], "火山 ASR Web UI 配置快照"),
            ("config", self.webui_api_update_config, ["POST"], "火山 ASR Web UI 更新配置"),
            ("emotions", self.webui_api_emotions, ["GET"], "火山 ASR 情绪云图数据"),
            ("emotions/clear", self.webui_api_clear_emotions, ["POST"], "清空火山 ASR 情绪缓存"),
        )
        for endpoint, handler, methods, desc in routes:
            route = f"/{PLUGIN_NAME}/{endpoint}"
            try:
                register_web_api(route, handler, methods, desc)
            except Exception as exc:
                logger.warning(
                    "注册火山 ASR Web UI API 失败，已跳过 %s，不影响语音识别主功能：%s",
                    route,
                    exc,
                )

    @staticmethod
    def _close_old_client(client: VolcBigModelAsrClient) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                asyncio.run(client.close())
            except RuntimeError:
                logger.warning("旧 ASR HTTP client 未能立即关闭，将等待插件退出时由进程回收。")
            return
        loop.create_task(client.close())

    @filter.command("volc_asr_status", alias={"火山语音状态"})
    async def volc_asr_status(self, event: AstrMessageEvent):
        """查看火山引擎语音识别插件配置状态。"""
        state = self.get_webui_state()
        yield event.plain_result(
            "火山引擎语音识别插件状态："
            f"\n版本：{state['version']}"
            f"\n仓库：{state['repo']}"
            f"\n鉴权：{'已配置' if state['auth_configured'] else '未配置'}"
            f"\n提交方式：{state['submit_mode_label']}"
            f"\n处理方式：{state['handling_mode']}"
            f"\n自动转码：{'启用' if state['enable_transcode'] else '关闭'}"
            f"\n转码输出：{state['transcode_output_format']}"
            f"\nffmpeg来源：{state['ffmpeg_source']}"
            f"\nffmpeg状态：{state['ffmpeg_status']}"
            f"\n私聊：{'启用' if state['enable_private'] else '关闭'}"
            f"\n群聊：{'启用' if state['enable_group'] else '关闭'}"
            f"\n最大音频：{state['max_audio_mb']} MB"
            f"\n情绪判断：{'启用' if state['emotion']['enabled'] else '关闭'}"
            f"\n情绪模型：{state['emotion']['model_id']}"
            f"\n情绪最大参考权重：{state['emotion']['max_respect_weight_percent']}%"
            "\n官方预处理提示：preprocess_stage 的 Voice processing failed 发生在插件 handler 之前；"
            "若关闭插件仍出现，请检查 AstrBot 官方 STT/预处理、NapCat get_record 或 Docker 共享卷。"
        )

    @filter.command("volc_asr_doctor", alias={"火山语音诊断"})
    async def volc_asr_doctor(self, event: AstrMessageEvent):
        """输出适合部署排障的一键诊断摘要。"""
        report = self.get_health_report()
        lines = [
            "火山 ASR 诊断报告：",
            f"版本：{report['version']}",
            f"总体状态：{report['summary']['level']} - {report['summary']['text']}",
        ]
        for check in report["checks"]:
            lines.append(f"- [{check['level']}] {check['title']}：{check['message']}")
            suggestion = check.get("suggestion", "")
            if suggestion:
                lines.append(f"  建议：{suggestion}")
        yield event.plain_result("\n".join(lines))

    def get_webui_state(self) -> dict[str, Any]:
        """Return a stable status/config snapshot reserved for future Web UI pages.

        Future Web UI code should use this method instead of reading plugin attributes directly.
        """
        auth_error = self.client.validate()
        return {
            "schema_version": 1,
            "version": PLUGIN_VERSION,
            "repo": PLUGIN_REPO_URL,
            "auth_configured": not auth_error,
            "auth_mode": "api_key" if self.client.api_key else "app_key_access_key" if self.client.app_key and self.client.access_key else "none",
            "validation_error": auth_error,
            "endpoint": self.client.endpoint,
            "resource_id": self.client.resource_id,
            "timeout_seconds": self.client.timeout_seconds,
            "submit_mode": self.submit_mode,
            "submit_mode_label": "URL 直传" if self.submit_mode == "url" else "Base64 上传",
            "handling_mode": (
                "注入为用户输入"
                if self.inject_as_user_input and not self.reply_transcription
                else "直接回复转写"
            ),
            "auto_recognize": self.auto_recognize,
            "enable_private": self.enable_private,
            "enable_group": self.enable_group,
            "only_when_at_or_wake": self.only_when_at_or_wake,
            "ignore_self": self.ignore_self,
            "enable_transcode": self.enable_transcode,
            "transcode_output_format": self.transcode_output_format,
            "transcode_sample_rate": self.transcode_sample_rate,
            "transcode_channels": self.transcode_channels,
            "prefer_bundled_ffmpeg": self.prefer_bundled_ffmpeg,
            "ffmpeg_path": self.ffmpeg_path,
            "ffmpeg_source": self.ffmpeg_source,
            "ffmpeg_status": (
                "未探测（自动转码关闭）"
                if not self.enable_transcode
                else "不可用"
                if self.ffmpeg_error
                else "可用"
            ),
            "ffmpeg_error": self.ffmpeg_error,
            "max_audio_mb": _max_mb_text(self.max_audio_bytes),
            "enable_itn": self.client.enable_itn,
            "enable_punc": self.client.enable_punc,
            "enable_ddc": self.client.enable_ddc,
            "enable_speaker_info": self.client.enable_speaker_info,
            "livingmemory_safe": self.inject_as_user_input and not self.reply_transcription,
            "emotion": {
                "enabled": self.enable_emotion_analysis,
                "model_id": self.emotion_model_id or "当前会话主 LLM",
                "context_turns": self.emotion_context_turns,
                "context_char_limit": self.emotion_context_char_limit,
                "max_respect_weight_percent": int(self.emotion_max_respect_weight * 100),
                "timeout_seconds": self.emotion_timeout_seconds,
                "fail_open": self.emotion_fail_open,
                "history_count": len(self._emotion_history),
                "history_limit": self.webui_emotion_history_limit,
            },
            "token_risk": self.token_risk_policy.to_dict(),
            "config": {
                "reply_transcription": self.reply_transcription,
                "inject_as_user_input": self.inject_as_user_input,
                "stop_event_after_recognition": self.stop_event_after_recognition,
                "send_empty_result_message": self.send_empty_result_message,
                "notify_config_error": self.notify_config_error,
                "notify_asr_error": self.notify_asr_error,
                "show_logid": self.show_logid,
            },
        }

    def get_health_report(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add_check(
            key: str,
            level: str,
            title: str,
            message: str,
            suggestion: str = "",
            **extra: Any,
        ) -> None:
            checks.append(
                {
                    "key": key,
                    "level": level,
                    "title": title,
                    "message": message,
                    "suggestion": suggestion,
                    **extra,
                }
            )

        auth_error = self.client.validate()
        add_check(
            "auth",
            "ok" if not auth_error else "error",
            "火山鉴权",
            "已配置可用鉴权。" if not auth_error else auth_error,
            "填写 api_key，或同时填写旧版 app_key/access_key。" if auth_error else "",
        )
        add_check(
            "ffmpeg",
            "ok" if (not self.enable_transcode or not self.ffmpeg_error) else "error",
            "ffmpeg 转码",
            self.ffmpeg_source if not self.ffmpeg_error else self.ffmpeg_error,
            "使用 Release 附件包体安装，或安装系统 ffmpeg 并配置 ffmpeg_path。" if self.ffmpeg_error else "",
            path=self.ffmpeg_path,
            source=self.ffmpeg_source,
        )
        add_check(
            "mode",
            "ok" if self.inject_as_user_input and not self.reply_transcription else "warn",
            "LivingMemory 分层",
            (
                "当前为干净转写进入记忆层，语音提示进入 LLM 层。"
                if self.inject_as_user_input and not self.reply_transcription
                else "当前不是推荐的注入模式，长期记忆或后续插件可能读到非预期文本。"
            ),
            "建议保持 inject_as_user_input=true 且 reply_transcription=false。",
        )
        add_check(
            "token_risk_guard",
            "ok" if self.token_risk_policy.enabled else "warn",
            "Token 风险保护",
            (
                f"已启用，阈值 medium/high/critical="
                f"{self.token_risk_policy.medium_tokens}/"
                f"{self.token_risk_policy.high_tokens}/"
                f"{self.token_risk_policy.critical_tokens}。"
                if self.token_risk_policy.enabled
                else "未启用，超长上下文可能继续进入主 LLM。"
            ),
            "建议保持启用，尤其是长期记忆和多插件环境。",
        )
        add_check(
            "emotion",
            "ok" if self.enable_emotion_analysis else "info",
            "情绪层",
            (
                "已启用情绪判断，结果只作为会话语气辅助。"
                if self.enable_emotion_analysis
                else "未启用情绪判断，插件只做 ASR 与基础注入。"
            ),
            "开启前请确认可接受额外 token、延迟和误判风险。" if not self.enable_emotion_analysis else "",
        )
        add_check(
            "duplicate_plugins",
            "info",
            "重复插件目录",
            "插件无法直接枚举宿主 plugins 目录，但 /volc_asr_status 只应返回一次。",
            "如果状态命令返回多次，请清理 plugin_upload_* 旧目录并重启 AstrBot 容器。",
        )
        levels = [check["level"] for check in checks]
        if "error" in levels:
            summary = {"level": "error", "text": "存在需要先处理的错误。"}
        elif "warn" in levels:
            summary = {"level": "warn", "text": "可运行，但存在部署或成本风险。"}
        else:
            summary = {"level": "ok", "text": "核心链路配置看起来正常。"}
        return {
            "schema_version": 1,
            "version": PLUGIN_VERSION,
            "repo": PLUGIN_REPO_URL,
            "summary": summary,
            "checks": checks,
        }

    def get_webui_config_schema(self) -> dict[str, Any]:
        """Return the plugin config schema reserved for future Web UI forms."""
        return _read_json_file(WEBUI_CONFIG_SCHEMA_PATH)

    def get_webui_config_snapshot(self) -> dict[str, Any]:
        """Return current config values for future Web UI editing surfaces."""
        schema = self.get_webui_config_schema()
        snapshot: dict[str, Any] = {}
        for key in WEBUI_CONFIG_KEYS:
            value = self.config.get(key, (schema.get(key) or {}).get("default", ""))
            snapshot[key] = _mask_secret(value) if key in WEBUI_SECRET_CONFIG_KEYS else value
        return snapshot

    def update_webui_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Apply validated config updates reserved for future Web UI save actions."""
        if not isinstance(updates, dict):
            return {"applied": {}, "skipped": {}, "errors": {"updates": "updates 必须是对象"}}

        schema = self.get_webui_config_schema()
        applied: dict[str, Any] = {}
        skipped: dict[str, str] = {}
        errors: dict[str, str] = {}
        needs_client_reload = False

        for key, value in updates.items():
            if key not in WEBUI_CONFIG_KEYS:
                skipped[key] = "未知配置项"
                continue
            if key in WEBUI_SECRET_CONFIG_KEYS and _is_unchanged_masked_secret(
                value,
                self.config.get(key),
            ):
                skipped[key] = "密钥未变更"
                continue

            ok, coerced, error = _coerce_webui_config_value(key, value, schema)
            if not ok:
                errors[key] = error
                continue

            self.config[key] = coerced
            applied[key] = _mask_secret(coerced) if key in WEBUI_SECRET_CONFIG_KEYS else coerced
            if key in WEBUI_CLIENT_CONFIG_KEYS:
                needs_client_reload = True

        if applied:
            self._reload_runtime_config(recreate_client=needs_client_reload)

        return {"applied": applied, "skipped": skipped, "errors": errors}

    def get_webui_emotion_cloud(self) -> dict[str, Any]:
        records = [record.to_dict() for record in self._emotion_history]
        label_counts: dict[str, int] = {label: 0 for label in sorted(EMOTION_LABELS)}
        for record in records:
            label = str(record.get("label") or "neutral")
            label_counts[label] = label_counts.get(label, 0) + 1
        return {
            "schema_version": 1,
            "count": len(records),
            "limit": self.webui_emotion_history_limit,
            "axes": {
                "x": "valence",
                "y": "arousal",
                "x_label": "效价 Valence",
                "y_label": "唤醒 Arousal",
            },
            "labels": sorted(EMOTION_LABELS),
            "label_names": {
                label: EMOTION_LABEL_NAMES.get(label, label)
                for label in sorted(EMOTION_LABELS)
            },
            "label_counts": label_counts,
            "records": records,
        }

    def clear_webui_emotion_history(self) -> dict[str, Any]:
        cleared = len(self._emotion_history)
        self._emotion_history.clear()
        return {"cleared": cleared, "count": 0, "limit": self.webui_emotion_history_limit}

    def _remember_emotion_judgement(
        self,
        event: AstrMessageEvent,
        judgement: EmotionJudgement,
        transcription_text: str,
    ) -> EmotionHistoryRecord:
        record = _build_emotion_history_record(event, judgement, transcription_text)
        self._emotion_history.append(record)
        return record

    @staticmethod
    def _json_response(payload: dict[str, Any], status_code: int = 200):
        try:
            from quart import jsonify
        except Exception:
            return payload
        response = jsonify(payload)
        response.status_code = status_code
        return response

    @staticmethod
    async def _request_json() -> dict[str, Any]:
        try:
            from quart import request
        except Exception:
            return {}
        try:
            data = await request.get_json(silent=True)
        except TypeError:
            data = await request.get_json()
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    async def webui_api_state(self):
        return self._json_response({"status": "ok", "data": self.get_webui_state()})

    async def webui_api_doctor(self):
        return self._json_response({"status": "ok", "data": self.get_health_report()})

    async def webui_api_config(self):
        return self._json_response(
            {
                "status": "ok",
                "data": {
                    "schema": self.get_webui_config_schema(),
                    "values": self.get_webui_config_snapshot(),
                },
            }
        )

    async def webui_api_update_config(self):
        payload = await self._request_json()
        updates = payload.get("updates", payload)
        result = self.update_webui_config(updates)
        status = "ok" if not result["errors"] else "error"
        return self._json_response(
            {
                "status": status,
                "data": result,
                "state": self.get_webui_state(),
                "config": self.get_webui_config_snapshot(),
            },
            400 if result["errors"] else 200,
        )

    async def webui_api_emotions(self):
        return self._json_response({"status": "ok", "data": self.get_webui_emotion_cloud()})

    async def webui_api_clear_emotions(self):
        return self._json_response({"status": "ok", "data": self.clear_webui_emotion_history()})

    @filter.event_message_type(filter.EventMessageType.ALL, priority=10)
    async def on_message(self, event: AstrMessageEvent):
        """自动识别消息中的语音段，并将事件改写为干净转写文本。"""
        if not self.auto_recognize:
            return

        voice_inputs = self._collect_voice_inputs(event)
        if not voice_inputs:
            return

        if not self._allow_event(event):
            _stop_voice_event_with_plain_text(event, DEFAULT_UNCLEAR_MEMORY_TEXT)
            return

        config_error = self.client.validate()
        if config_error:
            logger.warning(config_error)
            _stop_voice_event_with_plain_text(event, config_error)
            if self.notify_config_error:
                yield event.plain_result(config_error)
            return

        batch = await self._recognize_voice_inputs(voice_inputs)
        results = batch.results
        errors = batch.errors
        unclear_count = batch.unclear_count

        inject_mode = self.inject_as_user_input and not self.reply_transcription

        if inject_mode and results:
            transcription_text = self._build_transcription_text(results)
            llm_text = self._build_llm_user_text(results)
            self._apply_voice_injection_plan(
                event,
                VoiceInjectionPlan(
                    memory_text=transcription_text,
                    llm_text=llm_text,
                    raw_text=transcription_text,
                    diagnostics=batch.diagnostics,
                ),
            )
            emotion_judgement = await self._analyze_emotion(event, transcription_text)
            if emotion_judgement is not None:
                event.set_extra(ASR_EXTRA_EMOTION_RESULT, emotion_judgement.to_dict())
                self._remember_emotion_judgement(event, emotion_judgement, transcription_text)
                llm_text = _append_emotion_guidance(llm_text, emotion_judgement)
            llm_text, token_risk = self._apply_token_risk_guard(
                llm_text,
                memory_text=transcription_text,
                emotion_judgement=emotion_judgement,
            )
            event.set_extra(ASR_EXTRA_LLM_TEXT, llm_text)
            event.set_extra(ASR_EXTRA_TOKEN_RISK, token_risk.to_dict())
            if token_risk.action == "skip_llm_injection":
                logger.warning(
                    "语音 LLM 注入因 token 风险被降级为仅保留转写："
                    f"{token_risk.reason} estimated={token_risk.estimated_prompt_tokens}"
                )
            _set_clean_provider_request(event, llm_text)
            provider_request = event.get_extra("provider_request", None)
            _disable_default_llm_reentry(event)
            logger.info(
                "已将语音识别结果注入为干净用户输入，"
                f"memory_text={transcription_text}, llm_text={llm_text}"
            )
            if _looks_like_provider_request(provider_request):
                yield provider_request
            return

        if (
            inject_mode
            and not results
            and unclear_count > 0
            and self.inject_on_unclear_voice
        ):
            unclear_llm_text, token_risk = self._apply_token_risk_guard(
                self.unclear_voice_prompt,
                memory_text=DEFAULT_UNCLEAR_MEMORY_TEXT,
            )
            self._apply_voice_injection_plan(
                event,
                VoiceInjectionPlan(
                    memory_text=DEFAULT_UNCLEAR_MEMORY_TEXT,
                    llm_text=unclear_llm_text,
                    raw_text="",
                    unclear=True,
                    diagnostics=batch.diagnostics,
                ),
            )
            event.set_extra(ASR_EXTRA_TOKEN_RISK, token_risk.to_dict())
            _set_clean_provider_request(event, unclear_llm_text)
            provider_request = event.get_extra("provider_request", None)
            _disable_default_llm_reentry(event)
            logger.info(
                "语音未识别到内容，已注入干净未听清事件文本，"
                f"llm_text={unclear_llm_text}"
            )
            if _looks_like_provider_request(provider_request):
                yield provider_request
            return

        reply = self._build_reply(results, errors)
        if reply:
            _stop_voice_event_with_plain_text(
                event,
                self._build_transcription_text(results) if results else reply,
                diagnostics=batch.diagnostics,
            )
            yield event.plain_result(reply)
            return

        _stop_voice_event_with_plain_text(
            event,
            DEFAULT_UNCLEAR_MEMORY_TEXT,
            diagnostics=batch.diagnostics,
        )

    async def terminate(self) -> None:
        await self.client.close()

    @filter.on_llm_request(priority=-10)
    async def apply_voice_prompt_template(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """在 livingmemory 处理完干净文本后，再把 LLM prompt 替换为语音模板。"""
        if event.get_extra(ASR_EXTRA_EMOTION_INTERNAL_CALL, False):
            return
        memory_text = event.get_extra(ASR_EXTRA_MEMORY_TEXT, "")
        llm_text = event.get_extra(ASR_EXTRA_LLM_TEXT, "")
        if event.get_extra("volcengine_asr_llm_prompt_applied", False):
            return
        if not isinstance(memory_text, str) or not isinstance(llm_text, str):
            return
        memory_text = memory_text.strip()
        llm_text = llm_text.strip()
        if not memory_text or not llm_text:
            return
        _replace_event_message_with_plain_text(event, memory_text)
        _sanitize_event_cached_content(event, memory_text, llm_text)

        provider_request = _resolve_provider_request_argument(event, req, args, kwargs)
        if not _looks_like_provider_request(provider_request):
            _ensure_clean_voice_event_for_agent(event)
            return

        _sanitize_provider_request(provider_request, memory_text, llm_text)

        prompt = getattr(provider_request, "prompt", "")
        if not isinstance(prompt, str):
            prompt = ""

        new_prompt, replaced = _replace_first_text(prompt, memory_text, llm_text)
        if not replaced:
            new_prompt = f"{llm_text}\n\n{prompt.strip()}" if prompt.strip() else llm_text
            logger.warning(
                "未能在 LLM prompt 中定位语音转写文本，已将语音提示词前置并保留原 prompt，"
                f"memory_text={memory_text}, prompt={prompt[:120]}"
            )

        provider_request.prompt = new_prompt
        event.set_extra("volcengine_asr_llm_prompt_applied", True)
        logger.info("已在 LLM 请求阶段应用语音提示词模板，长期记忆仍保留干净转写文本。")

    @on_agent_begin(priority=100)
    async def ensure_voice_event_clean_before_agent(
        self,
        event: AstrMessageEvent,
        run_context: Any | None = None,
    ) -> None:
        """在 AstrBot 构建 agent 前兜底清理旧 Record 缓存。"""
        if event.get_extra(ASR_EXTRA_EMOTION_INTERNAL_CALL, False):
            return
        _ensure_clean_voice_event_for_agent(event, run_context)

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
        records: list[Any] = []
        seen: set[int] = set()
        for chain in _iter_message_chains(event):
            for component in _message_chain_items(chain):
                if _is_record_component(component) and id(component) not in seen:
                    seen.add(id(component))
                    records.append(component)
        return records

    @staticmethod
    def _collect_voice_inputs(event: AstrMessageEvent) -> list[VoiceInput]:
        return [
            VoiceInput(
                index=index,
                record=record,
                sources=_extract_record_sources(record),
                event=event,
            )
            for index, record in enumerate(VolcengineAsrPlugin._find_records(event), start=1)
        ]

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

    async def _recognize_records(self, records: list[Any]) -> RecognitionBatch:
        return await self._recognize_voice_inputs(
            [
                VoiceInput(index=index, record=record, sources=_extract_record_sources(record))
                for index, record in enumerate(records, start=1)
            ]
        )

    async def _recognize_voice_inputs(self, voice_inputs: list[VoiceInput]) -> RecognitionBatch:
        batch = RecognitionBatch(results=[], errors=[])
        for voice_input in voice_inputs:
            diagnostic = voice_input.to_diagnostic()
            try:
                audio_payload = await self._build_audio_payload_result(voice_input)
                diagnostic.update(audio_payload.to_diagnostic())
                result = await self.client.recognize(audio_payload.payload)
                if result.text:
                    batch.results.append(result)
                else:
                    self._add_unclear_error(batch, voice_input.index, "未识别到有效内容")
            except UserVisibleError as exc:
                logger.warning(f"语音识别准备失败：{exc}")
                diagnostic.update({"error_code": "audio_prepare_failed", "error_message": str(exc)})
                if self.notify_asr_error:
                    batch.errors.append(f"第 {voice_input.index} 条语音处理失败：{exc}")
            except VolcAsrError as exc:
                diagnostic.update(
                    {
                        "error_code": exc.status_code or "asr_failed",
                        "error_message": str(exc),
                        "logid": exc.logid,
                        "request_id": exc.request_id,
                    }
                )
                self._handle_asr_error(batch, voice_input.index, exc)
            except Exception:
                logger.exception("语音识别出现未预期异常")
                diagnostic.update({"error_code": "unexpected_error", "error_message": "插件内部异常"})
                if self.notify_asr_error:
                    batch.errors.append(f"第 {voice_input.index} 条语音识别失败：插件内部异常。")
            finally:
                batch.diagnostics.append(diagnostic)
        return batch

    def _add_unclear_error(self, batch: RecognitionBatch, index: int, reason: str) -> None:
        batch.unclear_count += 1
        if self.send_empty_result_message and not self.inject_on_unclear_voice:
            batch.errors.append(f"第 {index} 条语音{reason}。")

    def _handle_asr_error(self, batch: RecognitionBatch, index: int, exc: VolcAsrError) -> None:
        logger.warning(
            "火山引擎 ASR 失败："
            f"status={exc.status_code} "
            f"logid={exc.logid} "
            f"request_id={exc.request_id} "
            f"error={exc}"
        )
        if exc.status_code == VOLC_SILENT_AUDIO_CODE:
            self._add_unclear_error(batch, index, "是静音音频")
            return
        if self.notify_asr_error:
            detail = str(exc)
            if self.show_logid and exc.logid:
                detail = f"{detail}（logid: {exc.logid}）"
            batch.errors.append(f"第 {index} 条语音识别失败：{detail}")

    async def _build_audio_payload(self, record: Any) -> dict[str, str]:
        voice_input = VoiceInput(index=1, record=record, sources=_extract_record_sources(record))
        return (await self._build_audio_payload_result(voice_input)).payload

    async def _build_audio_payload_result(self, voice_input: VoiceInput) -> AudioPayloadResult:
        sources = voice_input.sources
        if self.submit_mode == "url":
            for source in sources:
                if source.startswith(("http://", "https://")) and _source_suffix(source) in SUPPORTED_AUDIO_EXTS:
                    suffix = _source_suffix(source)
                    return AudioPayloadResult(
                        payload={"url": source},
                        source=source,
                        source_type="url",
                        input_suffix=suffix,
                        detected_suffix=suffix,
                        output_format="url",
                    )

        audio_bytes, source, source_type = await self._record_to_audio_bytes(
            voice_input.record,
            sources,
            voice_input.event,
        )
        input_suffix = _source_suffix(source)
        detected_suffix = _detect_audio_suffix(audio_bytes, source)
        input_bytes = len(audio_bytes)
        normalized_audio, output_format, transcoded = await self._normalize_audio_payload_bytes(
            audio_bytes,
            source,
            detected_suffix,
        )
        if len(normalized_audio) > self.max_audio_bytes:
            raise UserVisibleError(f"音频超过配置上限 {_max_mb_text(self.max_audio_bytes)} MB。")
        base64_audio = base64.b64encode(normalized_audio).decode("ascii")
        return AudioPayloadResult(
            payload={"data": base64_audio},
            source=source,
            source_type=source_type,
            input_suffix=input_suffix,
            detected_suffix=detected_suffix,
            input_bytes=input_bytes,
            output_format=output_format,
            output_bytes=len(normalized_audio),
            transcoded=transcoded,
        )

    async def _record_to_audio_bytes(
        self,
        record: Any,
        sources: list[str],
        event: AstrMessageEvent | None = None,
    ) -> tuple[bytes, str, str]:
        last_error: Exception | None = None
        for source in sources:
            try:
                if source.startswith("base64://"):
                    return base64.b64decode(source.removeprefix("base64://")), source, "base64"

                local_path = _source_to_local_path(source)
                if local_path is not None:
                    return await self._file_to_bytes(local_path), str(local_path), "local_path"

                if source.startswith(("http://", "https://")):
                    return await self._download_bytes(source), source, "download"
            except UserVisibleError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc

        convert_to_base64 = getattr(record, "convert_to_base64", None)
        if callable(convert_to_base64):
            try:
                base64_audio = await convert_to_base64()
                return base64.b64decode(str(base64_audio).removeprefix("base64://")), "base64://record", "record_converter"
            except Exception as exc:
                last_error = exc

        onebot_audio = await self._record_to_audio_bytes_via_onebot(event, sources)
        if onebot_audio is not None:
            return onebot_audio

        if last_error and sources:
            raise UserVisibleError("无法从消息中读取语音文件。请确认 NapCat/OneBot 可通过 get_record 取得原语音内容。") from last_error
        if last_error:
            raise UserVisibleError(str(last_error)) from last_error
        raise UserVisibleError("无法从消息中读取语音文件。")

    async def _record_to_audio_bytes_via_onebot(
        self,
        event: AstrMessageEvent | None,
        sources: list[str],
    ) -> tuple[bytes, str, str] | None:
        bot = getattr(event, "bot", None) if event is not None else None
        call_action = getattr(bot, "call_action", None)
        if not callable(call_action):
            return None

        for source in sources:
            if not source or source.startswith(("base64://", "http://", "https://", "file://")):
                continue
            if _source_to_local_path(source) is not None:
                continue
            for output_format in (self.transcode_output_format, "wav", "mp3", "amr"):
                try:
                    result = await call_action(
                        action="get_record",
                        file=source,
                        out_format=output_format,
                    )
                except TypeError:
                    try:
                        result = await call_action(
                            "get_record",
                            file=source,
                            out_format=output_format,
                        )
                    except Exception as exc:
                        logger.warning(f"OneBot get_record 获取语音失败：{exc}")
                        continue
                except Exception as exc:
                    logger.warning(f"OneBot get_record 获取语音失败：{exc}")
                    continue

                loaded = await self._load_onebot_record_result(result, source)
                if loaded is not None:
                    return loaded
        return None

    async def _load_onebot_record_result(
        self,
        result: Any,
        original_source: str,
    ) -> tuple[bytes, str, str] | None:
        candidate = _onebot_record_result_source(result)
        if not candidate:
            return None
        if candidate.startswith("base64://"):
            return (
                base64.b64decode(_base64_payload_text(candidate)),
                "base64://onebot_get_record",
                "onebot_get_record",
            )
        local_path = _source_to_local_path(candidate)
        if local_path is not None:
            return await self._file_to_bytes(local_path), str(local_path), "onebot_get_record"
        if candidate.startswith(("http://", "https://")):
            return await self._download_bytes(candidate), candidate, "onebot_get_record"
        if len(candidate) > 64:
            try:
                return base64.b64decode(_base64_payload_text(candidate)), "base64://onebot_get_record", "onebot_get_record"
            except Exception:
                pass
        logger.warning(f"OneBot get_record 返回了不可读取的语音来源：{candidate or original_source}")
        return None

    async def _file_to_bytes(self, path: Path) -> bytes:
        size = path.stat().st_size
        if size > self.max_audio_bytes:
            raise UserVisibleError(f"音频超过配置上限 {_max_mb_text(self.max_audio_bytes)} MB。")
        return await self._read_bytes(path)

    async def _download_bytes(self, url: str) -> bytes:
        chunks: list[bytes] = []
        total = 0
        try:
            async with self.client.stream("GET", url) as response:
                response.raise_for_status()
                self._raise_if_content_too_large(response)
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.max_audio_bytes:
                        raise UserVisibleError(f"音频超过配置上限 {_max_mb_text(self.max_audio_bytes)} MB。")
                    chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise UserVisibleError(f"下载语音文件失败：{exc}") from exc
        if not chunks:
            raise UserVisibleError("语音文件为空。")
        return b"".join(chunks)

    def _raise_if_content_too_large(self, response: httpx.Response) -> None:
        content_length = _safe_int(response.headers.get("content-length"))
        if content_length is not None and content_length > self.max_audio_bytes:
            raise UserVisibleError(f"音频超过配置上限 {_max_mb_text(self.max_audio_bytes)} MB。")

    async def _normalize_audio_payload_bytes(
        self,
        data: bytes,
        source: str,
        detected_suffix: str | None = None,
    ) -> tuple[bytes, str, bool]:
        suffix = detected_suffix or _detect_audio_suffix(data, source)
        if suffix in SUPPORTED_AUDIO_EXTS:
            return data, suffix.lstrip(".") or "raw", False
        transcoded = await self._maybe_transcode_audio(data, source)
        return transcoded, self.transcode_output_format, True

    async def _maybe_transcode_audio(self, data: bytes, source: str) -> bytes:
        suffix = _detect_audio_suffix(data, source)
        if suffix in SUPPORTED_AUDIO_EXTS:
            return data
        if not self.enable_transcode:
            suffix_text = suffix or "未知格式"
            raise UserVisibleError(f"音频格式 {suffix_text} 不受火山引擎支持，且未启用转码。")

        if suffix and suffix not in TRANSCODE_HINT_EXTS:
            logger.warning(f"音频格式 {suffix} 不在已知转码列表中，仍尝试使用 ffmpeg 转码。")

        return await self._transcode_audio(data, suffix)

    async def _transcode_audio(self, data: bytes, suffix: str) -> bytes:
        if self.ffmpeg_error:
            raise UserVisibleError(self.ffmpeg_error)

        output_format = self.transcode_output_format
        command = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-vn",
            "-ac",
            str(self.transcode_channels),
            "-ar",
            str(self.transcode_sample_rate),
        ]
        if output_format == "wav":
            command.extend(["-acodec", "pcm_s16le", "-f", "wav", "pipe:1"])
        elif output_format == "mp3":
            command.extend(["-f", "mp3", "pipe:1"])
        else:
            command.extend(["-f", "ogg", "pipe:1"])

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise UserVisibleError(
                f"ffmpeg 启动失败，无法转码 {suffix or '该'} 音频：{exc}。"
                "请安装系统 ffmpeg，或在配置中填写可执行的 ffmpeg_path。"
            ) from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(data),
                timeout=self.client.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise UserVisibleError("ffmpeg 转码超时。") from exc

        if process.returncode != 0 or not stdout:
            error_text = stderr.decode("utf-8", errors="ignore").strip()
            if len(error_text) > 160:
                error_text = error_text[:160] + "..."
            raise UserVisibleError(f"ffmpeg 转码失败：{error_text or '没有输出'}")

        if len(stdout) > self.max_audio_bytes:
            raise UserVisibleError(f"转码后的音频超过配置上限 {_max_mb_text(self.max_audio_bytes)} MB。")

        logger.info(
            f"已将语音从 {suffix or '未知格式'} 转码为 {output_format}，"
            f"{len(data)} bytes -> {len(stdout)} bytes。"
        )
        return stdout

    @staticmethod
    async def _read_bytes(path: Path) -> bytes:
        return await asyncio.to_thread(path.read_bytes)

    def _build_result_values(self, results: list[AsrResult]) -> dict[str, Any]:
        text = self._build_transcription_text(results)
        return {
            "text": text,
            "logid": ",".join(item.logid for item in results if item.logid),
            "request_id": ",".join(item.request_id for item in results),
            "duration_ms": results[0].duration_ms or "" if len(results) == 1 else "",
        }

    def _build_reply(self, results: list[AsrResult], errors: list[str]) -> str:
        parts: list[str] = []
        if results:
            parts.append(_format_with_fallback(self.reply_template, self._build_result_values(results)))
            if self.show_logid:
                logids = [item.logid for item in results if item.logid]
                if logids:
                    parts.append("logid: " + ", ".join(logids))

        if errors:
            parts.extend(errors)

        return "\n".join(part for part in parts if part).strip()

    async def _analyze_emotion(
        self,
        event: AstrMessageEvent,
        transcription_text: str,
    ) -> EmotionJudgement | None:
        if not self.enable_emotion_analysis or not transcription_text.strip():
            return None

        context_text = self._build_emotion_context(event)
        prompt = self.emotion_engine.prompt_builder.build_prompt(
            self.emotion_prompt_template,
            transcription_text=transcription_text,
            context_text=context_text,
        )
        prompt_risk = self.token_risk_policy.assess(
            prompt,
            context_text=context_text,
            transcription_text=transcription_text,
        )
        event.set_extra("volcengine_asr_emotion_prompt_risk", prompt_risk.to_dict())
        if prompt_risk.action == "skip_llm_injection":
            logger.warning(
                "情绪判断 LLM 因 token 风险跳过："
                f"{prompt_risk.reason} estimated={prompt_risk.estimated_prompt_tokens}"
            )
            return None
        if prompt_risk.action in {"compact_voice_prompt", "compact_emotion_guidance"}:
            compact_context = _compact_text_for_prompt(context_text, max(0, self.emotion_context_char_limit // 2))
            prompt = self.emotion_engine.prompt_builder.build_prompt(
                self.emotion_prompt_template,
                transcription_text=_compact_text_for_prompt(transcription_text, 1200),
                context_text=compact_context,
            )
        try:
            event.set_extra(ASR_EXTRA_EMOTION_INTERNAL_CALL, True)
            response_text = await self._invoke_emotion_llm(event, prompt)
        except Exception as exc:
            logger.warning(f"情绪判断 LLM 调用失败，已跳过情绪增强：{exc}")
            if self.emotion_fail_open:
                return None
            raise
        finally:
            event.set_extra(ASR_EXTRA_EMOTION_INTERNAL_CALL, False)

        data = _safe_parse_json_object(response_text)
        if data is None:
            logger.warning(f"情绪判断 LLM 未返回合法 JSON，已跳过情绪增强：{response_text[:200]}")
            if self.emotion_fail_open:
                return None
            raise RuntimeError("情绪判断 LLM 未返回合法 JSON")

        judgement = self.emotion_engine.scorer.build_judgement(
            data,
            transcript_chars=len(transcription_text),
            max_respect_weight=self.emotion_max_respect_weight,
            weighting_policy=self.emotion_weighting_policy,
        )
        event.set_extra(ASR_EXTRA_EMOTION_APPLIED, True)
        logger.info(
            "已完成语音情绪判断："
            f"label={judgement.label}, respect_weight={judgement.respect_weight}"
        )
        return judgement

    def _build_emotion_context(self, event: AstrMessageEvent) -> str:
        if self.emotion_context_turns <= 0:
            return ""
        candidates = []
        for attr in ("message_str", "raw_message", "message"):
            value = getattr(event, attr, None)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        message_obj = getattr(event, "message_obj", None)
        if message_obj is not None:
            value = getattr(message_obj, "message_str", None)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
        unique: list[str] = []
        for item in candidates:
            if item not in unique:
                unique.append(item)
        context = "\n".join(unique[-self.emotion_context_turns :])
        if self.emotion_context_char_limit <= 0:
            return ""
        return _compact_text_for_prompt(context, self.emotion_context_char_limit)

    async def _invoke_emotion_llm(self, event: AstrMessageEvent, prompt: str) -> str:
        provider_id = self.emotion_model_id
        if not provider_id:
            get_provider_id = getattr(self.context, "get_current_chat_provider_id", None)
            if callable(get_provider_id):
                umo = getattr(event, "unified_msg_origin", None)
                provider_id = await get_provider_id(umo=umo)

        llm_generate = getattr(self.context, "llm_generate", None)
        if not callable(llm_generate):
            raise RuntimeError("当前 AstrBot Context 不支持 llm_generate")

        kwargs: dict[str, Any] = {"prompt": prompt}
        if provider_id:
            kwargs["chat_provider_id"] = provider_id

        response = await asyncio.wait_for(
            llm_generate(**kwargs),
            timeout=self.emotion_timeout_seconds,
        )
        for attr in ("completion_text", "text", "content", "result"):
            value = getattr(response, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(response, str):
            return response.strip()
        return str(response).strip()

    def _build_transcription_text(self, results: list[AsrResult]) -> str:
        if len(results) == 1:
            return results[0].text
        return "\n".join(f"{index}. {item.text}" for index, item in enumerate(results, start=1))

    def _build_llm_user_text(self, results: list[AsrResult]) -> str:
        return _render_prompt_template(self.voice_prompt_template, self._build_result_values(results))

    def _apply_token_risk_guard(
        self,
        llm_text: str,
        *,
        memory_text: str,
        emotion_judgement: EmotionJudgement | None = None,
    ) -> tuple[str, TokenRiskAssessment]:
        assessment = self.token_risk_policy.assess(
            llm_text,
            transcription_text=memory_text,
        )
        if assessment.action == "compact_emotion_guidance" and emotion_judgement is not None:
            compact = _append_compact_emotion_guidance(
                _render_prompt_template(
                    self.voice_prompt_template,
                    {"text": memory_text, "logid": "", "request_id": "", "duration_ms": ""},
                ),
                emotion_judgement,
            )
            return compact, assessment.with_final_prompt(compact)
        if assessment.action == "compact_voice_prompt":
            compact = (
                f"{memory_text.strip()}\n\n"
                "[语音转写提示：这是用户语音转文字结果。请自然回复，不要讨论转写机制。]"
            ).strip()
            if emotion_judgement is not None:
                compact = _append_compact_emotion_guidance(compact, emotion_judgement)
            return compact, assessment.with_final_prompt(compact)
        if assessment.action == "skip_llm_injection":
            compact = memory_text.strip()
            return compact, assessment.with_final_prompt(compact)
        return llm_text, assessment.with_final_prompt(llm_text)

    @staticmethod
    def _apply_voice_injection_plan(event: AstrMessageEvent, plan: VoiceInjectionPlan) -> None:
        plan.apply_to_event(event)

    @staticmethod
    def _inject_user_text(
        event: AstrMessageEvent,
        *,
        memory_text: str,
        llm_text: str,
        raw_text: str,
        unclear: bool = False,
    ) -> None:
        VolcengineAsrPlugin._apply_voice_injection_plan(
            event,
            VoiceInjectionPlan(
                memory_text=memory_text,
                llm_text=llm_text,
                raw_text=raw_text,
                unclear=unclear,
            ),
        )
