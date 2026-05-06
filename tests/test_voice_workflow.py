import asyncio

import astrbot.api.message_components as Comp

from astrbot_plugin_volcengine_asr.main import (
    ASR_EXTRA_DIAGNOSTICS,
    ASR_EXTRA_EMOTION_INTERNAL_CALL,
    ASR_EXTRA_INJECTED,
    ASR_EXTRA_LLM_TEXT,
    ASR_EXTRA_MEMORY_TEXT,
    ASR_EXTRA_UNCLEAR,
    DEFAULT_UNCLEAR_MEMORY_TEXT,
    AsrResult,
    RecognitionBatch,
    UserVisibleError,
    VolcengineAsrPlugin,
)


class _FakeEvent:
    def __init__(self, records=None, *, group_id="", sender_id="user", self_id="bot"):
        self.extras = {}
        self.message_str = ""
        self.message = list(records or [])
        self.message_chain = list(self.message)
        self.raw_message = {"message": list(self.message)}
        self.stopped = 0
        self.replies = []
        self.is_at_or_wake_command = True
        self.unified_msg_origin = "umo"
        self.message_obj = type("MessageObj", (), {})()
        self.message_obj.group_id = group_id
        self.message_obj.self_id = self_id
        self.message_obj.sender = type("Sender", (), {"user_id": sender_id})()
        self.message_obj.message_str = ""
        self.message_obj.message = list(self.message)
        self.message_obj.message_chain = list(self.message)
        self.message_obj.raw_message = {"raw_message": list(self.message)}
        self.message_obj.extras = {}

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def get_messages(self):
        return self.message_obj.message

    def stop_event(self):
        self.stopped += 1

    def plain_result(self, text):
        result = {"type": "plain_result", "text": text}
        self.replies.append(result)
        return result


class _FakeProviderRequest:
    def __init__(self, prompt=""):
        self.prompt = prompt
        self.audio_urls = ["old.amr"]
        self.files = ["old.amr"]
        self.contexts = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "上下文"},
                    {"type": "audio_url", "audio_url": "old.amr"},
                ],
            }
        ]
        self.extra_user_content_parts = [
            {"type": "text", "text": "[Audio Attachment: path old.amr]"},
            {"type": "text", "text": "保留"},
        ]
        self.messages = [
            {
                "role": "user",
                "content": [
                    {"type": "audio_url", "audio_url": "old.amr"},
                    {"type": "text", "text": "旧消息"},
                ],
            }
        ]


async def _collect_asyncgen(async_gen):
    items = []
    async for item in async_gen:
        items.append(item)
    return items


def _make_plugin(**config):
    merged = {
        "api_key": "token",
        "enable_transcode": False,
        "voice_prompt_template": "<text>[语音提示]",
    }
    merged.update(config)
    return VolcengineAsrPlugin(None, merged)


def test_on_message_success_rebuilds_event_and_provider_request():
    record = Comp.Record(file="2f7e2f96f5d363c6311f8bacdaafea11.amr")
    event = _FakeEvent([record])
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(voice_inputs):
        return RecognitionBatch(
            results=[AsrResult(text="你好", request_id="req-1", logid="log-1")],
            errors=[],
            diagnostics=[{"index": voice_inputs[0].index, "source_type": "record_converter"}],
        )

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert outputs == []
    assert event.stopped == 0
    assert event.message_str == "你好"
    assert event.message_obj.message_str == "你好"
    assert event.message[0].text == "你好"
    assert event.message_obj.message[0].text == "你好"
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.get_extra(ASR_EXTRA_MEMORY_TEXT) == "你好"
    assert event.get_extra(ASR_EXTRA_LLM_TEXT) == "你好[语音提示]"
    assert event.get_extra(ASR_EXTRA_INJECTED) is True
    assert event.get_extra(ASR_EXTRA_DIAGNOSTICS)[0]["source_type"] == "record_converter"

    req = _FakeProviderRequest(prompt="包装 你好 结束")
    asyncio.run(plugin.apply_voice_prompt_template(event, req))

    assert req.prompt == "包装 你好[语音提示] 结束"
    assert req.audio_urls == []
    assert req.files == []
    assert req.contexts == [{"role": "user", "content": [{"type": "text", "text": "上下文"}]}]
    assert req.extra_user_content_parts == [{"type": "text", "text": "保留"}]


def test_apply_voice_prompt_template_takes_over_when_prompt_does_not_contain_memory_text():
    plugin = _make_plugin()
    event = _FakeEvent()
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "干净文本")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "LLM 文本")
    req = _FakeProviderRequest(prompt="完全不包含目标文本")

    asyncio.run(plugin.apply_voice_prompt_template(event, req))

    assert req.prompt == "LLM 文本\n\n完全不包含目标文本"
    assert req.audio_urls == []


def test_apply_voice_prompt_template_skips_emotion_internal_call():
    plugin = _make_plugin()
    event = _FakeEvent()
    event.set_extra(ASR_EXTRA_EMOTION_INTERNAL_CALL, True)
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "干净文本")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "LLM 文本")
    req = _FakeProviderRequest(prompt="干净文本")

    asyncio.run(plugin.apply_voice_prompt_template(event, req))

    assert req.prompt == "干净文本"
    assert req.audio_urls == ["old.amr"]


def test_on_message_unclear_voice_injects_unclear_plan():
    event = _FakeEvent([Comp.Record(file="voice.amr")])
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(
            results=[],
            errors=[],
            unclear_count=1,
            diagnostics=[{"index": 1, "error_code": "silent"}],
        )

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert outputs == []
    assert event.stopped == 0
    assert event.message_str == DEFAULT_UNCLEAR_MEMORY_TEXT
    assert event.get_extra(ASR_EXTRA_UNCLEAR) is True
    assert event.get_extra(ASR_EXTRA_INJECTED) is True


def test_on_message_reply_mode_stops_after_success_when_configured():
    event = _FakeEvent([Comp.Record(file="voice.amr")])
    plugin = _make_plugin(reply_transcription=True, inject_as_user_input=False)

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(
            results=[AsrResult(text="你好", request_id="req-1")],
            errors=[],
        )

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert outputs[0]["text"] == "语音转文字：你好"
    assert event.stopped == 1
    assert event.get_extra(ASR_EXTRA_INJECTED) is None


def test_on_message_error_stops_to_prevent_old_record_from_reaching_agent():
    event = _FakeEvent([Comp.Record(file="voice.amr")])
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(results=[], errors=["第 1 条语音处理失败：ffmpeg 启动失败"])

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert "ffmpeg 启动失败" in outputs[0]["text"]
    assert event.stopped == 1
    assert event.get_extra(ASR_EXTRA_INJECTED) is None


def test_build_audio_payload_url_mode_does_not_trust_amr_url():
    plugin = _make_plugin(submit_mode="url")
    record = Comp.Record(url="https://example.com/voice.amr")

    async def fake_download_bytes(url):
        assert url == "https://example.com/voice.amr"
        return b"#!AMR\nvoice"

    async def fake_transcode_audio(data, suffix):
        assert suffix == ".amr"
        return b"RIFFxxxxWAVEfmt "

    plugin._download_bytes = fake_download_bytes
    plugin._transcode_audio = fake_transcode_audio
    plugin.enable_transcode = True

    payload = asyncio.run(plugin._build_audio_payload_result(plugin._collect_voice_inputs(_FakeEvent([record]))[0]))

    assert "data" in payload.payload
    assert payload.source_type == "download"
    assert payload.detected_suffix == ".amr"
    assert payload.transcoded is True
    assert payload.output_format == "wav"


def test_build_audio_payload_reports_user_visible_audio_errors():
    plugin = _make_plugin()
    record = Comp.Record(file="missing.amr")

    async def fake_record_to_audio_bytes(_record, _sources):
        raise UserVisibleError("无法从消息中读取语音文件。")

    plugin._record_to_audio_bytes = fake_record_to_audio_bytes

    batch = asyncio.run(plugin._recognize_voice_inputs(plugin._collect_voice_inputs(_FakeEvent([record]))))

    assert batch.errors == ["第 1 条语音处理失败：无法从消息中读取语音文件。"]
    assert batch.diagnostics[0]["error_code"] == "audio_prepare_failed"


def test_bare_amr_file_conversion_failure_is_reported_and_stopped():
    record = Comp.Record(file="2f7e2f96f5d363c6311f8bacdaafea11.amr")
    event = _FakeEvent([record])
    plugin = _make_plugin()

    batch = asyncio.run(plugin._recognize_voice_inputs(plugin._collect_voice_inputs(event)))

    assert batch.results == []
    assert batch.diagnostics[0]["error_code"] == "audio_prepare_failed"
    assert "语音处理失败" in batch.errors[0]

    async def fake_recognize_voice_inputs(_voice_inputs):
        return batch

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs
    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert "语音处理失败" in outputs[0]["text"]
    assert event.stopped == 1
