import asyncio
import base64

import astrbot.api.message_components as Comp

from astrbot_plugin_volcengine_asr.main import (
    ASR_EXTRA_DIAGNOSTICS,
    ASR_EXTRA_EMOTION_INTERNAL_CALL,
    ASR_EXTRA_EMOTION_RESULT,
    ASR_EXTRA_INJECTED,
    ASR_EXTRA_LLM_TEXT,
    ASR_EXTRA_MEMORY_TEXT,
    ASR_EXTRA_UNCLEAR,
    DEFAULT_UNCLEAR_MEMORY_TEXT,
    AsrResult,
    EmotionWeightingInput,
    RecognitionBatch,
    UserVisibleError,
    VolcengineAsrPlugin,
    _ensure_clean_voice_event_for_agent,
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
        self.calls = []
        self.is_at_or_wake_command = True
        self.call_llm = False
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

    def get_message_str(self):
        return self.message_str

    def stop_event(self):
        self.calls.append("stop_event")
        self.stopped += 1

    def plain_result(self, text):
        self.calls.append("plain_result")
        result = {"type": "plain_result", "text": text}
        self.replies.append(result)
        return result

    def should_call_llm(self, call_llm):
        self.calls.append(("should_call_llm", call_llm))
        self.call_llm = call_llm


class _FakeProviderRequest:
    def __init__(self, prompt=""):
        self.prompt = prompt
        self.audio_urls = ["old.amr"]
        self.files = ["old.amr"]
        self.contexts = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "context"},
                    {"type": "audio_url", "audio_url": "old.amr"},
                ],
            }
        ]
        self.extra_user_content_parts = [
            {"type": "text", "text": "[Audio Attachment: path old.amr]"},
            {"type": "text", "text": "keep"},
        ]
        self.messages = [
            {
                "role": "user",
                "content": [
                    {"type": "audio_url", "audio_url": "old.amr"},
                    {"type": "text", "text": "old message"},
                ],
            }
        ]
        self.cached_content = [{"type": "record", "data": {"file": "cached-content.amr"}}]
        self.cached_messages = [{"type": "record", "data": {"file": "cached-messages.amr"}}]
        self.history = [{"type": "record", "data": {"file": "history.amr"}}]

    def model_dump_for_context(self):
        return {"prompt": self.prompt}


class _ContextOnlyProviderRequest:
    def __init__(self):
        self.audio_urls = ["context-only.amr"]
        self.files = ["context-only.amr"]
        self.messages = [{"role": "user", "content": [{"type": "record", "data": {"file": "hidden.amr"}}]}]

    def model_dump_for_context(self):
        return {"messages": self.messages}


class _FakeContentPart:
    type = "text"

    def __init__(self, text):
        self.text = text

    def model_dump_for_context(self):
        return {"type": self.type, "text": self.text}


class _FakeRunContext:
    def __init__(self, event=None):
        self.event = event
        self.provider_request = _FakeProviderRequest(prompt="cached.amr")
        self.messages = [
            {"role": "user", "content": [{"type": "record", "data": {"file": "run-context.amr"}}]}
        ]
        self.stage_data = {
            "payload": {"message": [{"type": "record", "data": {"file": "stage-data.amr"}}]}
        }
        self.cache = {"provider_request": _FakeProviderRequest(prompt="cache-provider.amr")}
        self.cached_content = [{"type": "record", "data": {"file": "object-cached.amr"}}]
        self.cached_messages = [{"type": "record", "data": {"file": "object-cached-messages.amr"}}]


class _NonIterableMessageChain:
    def __init__(self, items):
        self.chain = list(items)


class _OneBotRecord:
    def __init__(self, file):
        self.type = "record"
        self.file = file

    async def convert_to_base64(self):
        raise Exception(f"not a valid file: {self.file}")


class _FakeOneBot:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def call_action(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


async def _collect_asyncgen(async_gen):
    items = []
    async for item in async_gen:
        items.append(item)
    return items


def _make_plugin(**config):
    merged = {
        "api_key": "token",
        "enable_transcode": False,
        "voice_prompt_template": "<text>[voice prompt]",
    }
    merged.update(config)
    return VolcengineAsrPlugin(None, merged)


def test_allow_event_decision_matrix():
    assert _make_plugin()._allow_event(_FakeEvent()) is True
    assert _make_plugin(enable_private=False)._allow_event(_FakeEvent()) is False

    group_event = _FakeEvent(group_id="group-1")
    assert _make_plugin(enable_group=True)._allow_event(group_event) is True
    assert _make_plugin(enable_group=False)._allow_event(group_event) is False

    wake_event = _FakeEvent()
    wake_event.is_at_or_wake_command = False
    assert _make_plugin(only_when_at_or_wake=True)._allow_event(wake_event) is False
    wake_event.is_at_or_wake_command = True
    assert _make_plugin(only_when_at_or_wake=True)._allow_event(wake_event) is True

    self_event = _FakeEvent(sender_id="bot", self_id="bot")
    assert _make_plugin(ignore_self=True)._allow_event(self_event) is False
    assert _make_plugin(ignore_self=False)._allow_event(self_event) is True


def test_on_message_success_rebuilds_event_and_provider_request():
    record = Comp.Record(file="2f7e2f96f5d363c6311f8bacdaafea11.amr")
    event = _FakeEvent([record])
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(voice_inputs):
        return RecognitionBatch(
            results=[AsrResult(text="hello", request_id="req-1", logid="log-1")],
            errors=[],
            diagnostics=[{"index": voice_inputs[0].index, "source_type": "record_converter"}],
        )

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert len(outputs) == 1
    assert outputs[0].prompt == "hello[voice prompt]"
    assert event.stopped == 0
    assert event.calls == [("should_call_llm", True)]
    assert event.call_llm is True
    assert event.message_str == "hello"
    assert event.get_message_str() == "hello"
    assert event.message_obj.message_str == "hello"
    assert event.message[0].text == "hello"
    assert event.message_obj.message[0].text == "hello"
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.get_extra(ASR_EXTRA_MEMORY_TEXT) == "hello"
    assert event.get_extra(ASR_EXTRA_LLM_TEXT) == "hello[voice prompt]"
    assert event.get_extra(ASR_EXTRA_INJECTED) is True
    assert event.get_extra(ASR_EXTRA_DIAGNOSTICS)[0]["source_type"] == "record_converter"

    provider_request = event.get_extra("provider_request")
    assert provider_request.prompt == "hello[voice prompt]"
    assert provider_request.audio_urls == []

    req = _FakeProviderRequest(prompt="wrap hello end")
    asyncio.run(plugin.apply_voice_prompt_template(event, req))

    assert req.prompt == "wrap hello[voice prompt] end"
    assert req.audio_urls == []
    assert req.files == []
    assert req.contexts == [{"role": "user", "content": [{"type": "text", "text": "context"}]}]
    assert req.extra_user_content_parts == [{"type": "text", "text": "keep"}]


def test_on_message_success_overrides_stale_get_message_str_for_livingmemory():
    record = Comp.Record(file="voice.amr")
    event = _FakeEvent([record])
    event._stale_message_str = ""

    def stale_get_message_str():
        return event._stale_message_str

    event.get_message_str = stale_get_message_str
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(results=[AsrResult(text="hello", request_id="req-1")], errors=[])

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert len(outputs) == 1
    assert event.message_str == "hello"
    assert event._stale_message_str == ""
    assert event.get_message_str() == "hello"
    event.message_str = ""
    assert event.get_message_str() == "hello"


def test_on_message_success_cleans_non_iterable_message_chain_object():
    record = Comp.Record(file="330898de94fe28ae378bdee1c2fe929f.amr")
    original_chain = _NonIterableMessageChain([record])
    event = _FakeEvent()
    event.message_obj.message = original_chain
    event.message = []
    event.message_chain = []
    event.raw_message = []
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(results=[AsrResult(text="hello", request_id="req-1")], errors=[])

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert len(outputs) == 1
    assert outputs[0].prompt == "hello[voice prompt]"
    assert VolcengineAsrPlugin._find_records(event) == []
    assert len(original_chain.chain) == 1
    assert original_chain.chain[0].text == "hello"
    assert event.get_extra("provider_request").prompt == "hello[voice prompt]"


def test_on_message_cleans_record_before_emotion_llm_call():
    record = Comp.Record(file="voice.amr")
    event = _FakeEvent([record])
    plugin = _make_plugin(enable_emotion_analysis=True)

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(results=[AsrResult(text="worry", request_id="req-1")], errors=[])

    class _FakeContext:
        async def get_current_chat_provider_id(self, umo=None):
            assert umo == "umo"
            return "provider-default"

        async def llm_generate(self, **kwargs):
            assert kwargs["chat_provider_id"] == "provider-default"
            assert VolcengineAsrPlugin._find_records(event) == []
            assert event.message_str == "worry"
            return (
                '{"label":"anxious","emotion_weights":{"anxious":0.8,"neutral":0.2},'
                '"confidence":0.7,"valence":-0.4,"arousal":0.6,'
                '"voice_text_support":0.8,"context_support":0.2,"reason":"user is worried"}'
            )

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs
    plugin.context = _FakeContext()

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert len(outputs) == 1
    assert event.stopped == 0
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.get_extra(ASR_EXTRA_EMOTION_RESULT)["label"] == "anxious"
    assert "anxious" in event.get_extra(ASR_EXTRA_LLM_TEXT)
    assert event.get_extra("provider_request").prompt == event.get_extra(ASR_EXTRA_LLM_TEXT)


def test_on_message_uses_plugin_emotion_weighting_policy():
    record = Comp.Record(file="voice.amr")
    event = _FakeEvent([record])
    plugin = _make_plugin(enable_emotion_analysis=True)

    class _FixedPolicy:
        def compute_respect_weight(self, data: EmotionWeightingInput) -> float:
            assert data.transcript_chars == len("worry")
            return 0.111

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(results=[AsrResult(text="worry", request_id="req-1")], errors=[])

    class _FakeContext:
        async def get_current_chat_provider_id(self, umo=None):
            return "provider-default"

        async def llm_generate(self, **kwargs):
            return (
                '{"label":"anxious","emotion_weights":{"anxious":1.0},'
                '"confidence":1.0,"voice_text_support":1.0,"context_support":1.0}'
            )

    plugin.emotion_weighting_policy = _FixedPolicy()
    plugin._recognize_voice_inputs = fake_recognize_voice_inputs
    plugin.context = _FakeContext()

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert len(outputs) == 1
    assert event.get_extra(ASR_EXTRA_EMOTION_RESULT)["respect_weight"] == 0.111


def test_apply_voice_prompt_template_takes_over_when_prompt_does_not_contain_memory_text():
    plugin = _make_plugin()
    event = _FakeEvent()
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "clean text")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "LLM text")
    req = _FakeProviderRequest(prompt="no target text")

    asyncio.run(plugin.apply_voice_prompt_template(event, req))

    assert req.prompt == "LLM text\n\nno target text"
    assert req.audio_urls == []
    assert event.get_message_str() == "clean text"


def test_apply_voice_prompt_template_preserves_content_part_objects():
    plugin = _make_plugin()
    event = _FakeEvent()
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "clean text")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "LLM text")
    part = _FakeContentPart("[Audio Attachment: path old.amr]")
    keep = _FakeContentPart("keep")
    req = _FakeProviderRequest(prompt="clean text")
    req.extra_user_content_parts = [part, keep]

    asyncio.run(plugin.apply_voice_prompt_template(event, req))

    assert req.extra_user_content_parts == [keep]
    assert part.text == "[Audio Attachment: path old.amr]"
    assert keep.text == "keep"
    assert all(hasattr(item, "model_dump_for_context") for item in req.extra_user_content_parts)


def test_apply_voice_prompt_template_skips_emotion_internal_call():
    plugin = _make_plugin()
    event = _FakeEvent()
    event.set_extra(ASR_EXTRA_EMOTION_INTERNAL_CALL, True)
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "clean text")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "LLM text")
    req = _FakeProviderRequest(prompt="clean text")

    asyncio.run(plugin.apply_voice_prompt_template(event, req))

    assert req.prompt == "clean text"
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

    assert len(outputs) == 1
    assert outputs[0].prompt == plugin.unclear_voice_prompt
    assert event.stopped == 0
    assert event.message_str == DEFAULT_UNCLEAR_MEMORY_TEXT
    assert event.message[0].text == DEFAULT_UNCLEAR_MEMORY_TEXT
    assert event.message_chain[0].text == DEFAULT_UNCLEAR_MEMORY_TEXT
    assert event.message_obj.message[0].text == DEFAULT_UNCLEAR_MEMORY_TEXT
    assert event.message_obj.message_chain[0].text == DEFAULT_UNCLEAR_MEMORY_TEXT
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.get_extra(ASR_EXTRA_UNCLEAR) is True
    assert event.get_extra(ASR_EXTRA_INJECTED) is True
    assert event.get_extra("provider_request").prompt == plugin.unclear_voice_prompt
    assert event.calls == [("should_call_llm", True)]


def test_on_message_reply_mode_stops_after_success_when_configured():
    event = _FakeEvent([Comp.Record(file="voice.amr")])
    plugin = _make_plugin(reply_transcription=True, inject_as_user_input=False)

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(
            results=[AsrResult(text="hello", request_id="req-1")],
            errors=[],
        )

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert outputs
    assert "hello" in outputs[0]["text"]
    assert event.stopped == 1
    assert event.calls[:2] == ["stop_event", "plain_result"]
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.get_extra(ASR_EXTRA_INJECTED) is False


def test_on_message_error_stops_to_prevent_old_record_from_reaching_agent():
    event = _FakeEvent([Comp.Record(file="voice.amr")])
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(results=[], errors=["voice prepare failed: ffmpeg startup failed"])

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert "ffmpeg startup failed" in outputs[0]["text"]
    assert event.stopped == 1
    assert event.calls[:2] == ["stop_event", "plain_result"]
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.get_extra(ASR_EXTRA_INJECTED) is False


def test_on_message_config_error_stops_before_plain_result():
    event = _FakeEvent([Comp.Record(file="voice.amr")])
    plugin = _make_plugin(api_key="", app_key="", access_key="")

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert outputs
    assert event.stopped == 1
    assert event.calls[:2] == ["stop_event", "plain_result"]
    assert VolcengineAsrPlugin._find_records(event) == []


def test_on_message_disallowed_voice_event_stops_and_cleans_record():
    event = _FakeEvent([Comp.Record(file="voice.amr")])
    event.is_at_or_wake_command = False
    plugin = _make_plugin(only_when_at_or_wake=True)

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert outputs == []
    assert event.stopped == 1
    assert event.calls == ["stop_event"]
    assert event.message_str == DEFAULT_UNCLEAR_MEMORY_TEXT
    assert VolcengineAsrPlugin._find_records(event) == []


def test_find_records_reads_nested_napcat_onebot_shapes():
    event = _FakeEvent()
    record_a = {"type": "record", "data": {"file": "from-data-message.amr"}}
    record_b = {"type": "record", "data": {"file": "from-segments.amr"}}
    record_c = {"type": "record", "data": {"file": "from-original.amr"}}
    event.message = []
    event.message_chain = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.raw_message = {
        "data": {"message": [record_a]},
        "segments": [record_b],
        "original_message": [record_c],
    }

    assert VolcengineAsrPlugin._find_records(event) == [record_a, record_b, record_c]


def test_find_records_reads_event_and_message_obj_extra_caches():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    record_a = {"type": "record", "data": {"file": "from-event-extras.amr"}}
    record_b = {"type": "record", "data": {"file": "from-message-extras.amr"}}
    event.extras["request"] = {"messages": [{"content": [record_a]}]}
    event.message_obj.extras["input"] = {"message": [record_b]}

    assert VolcengineAsrPlugin._find_records(event) == [record_b, record_a]


def test_agent_begin_cleanup_removes_records_from_extra_cache_shapes():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    event.extras["data"] = {"message": [{"type": "record", "data": {"file": "from-data.amr"}}]}
    event.extras["segments"] = [{"type": "record", "data": {"file": "from-segments.amr"}}]
    event.message_obj.extras["original_message"] = [
        {"type": "record", "data": {"file": "from-original.amr"}}
    ]
    event.extras["provider_request"] = _FakeProviderRequest(prompt="hello")
    event.extras["provider_request"].messages.append(
        {"role": "user", "content": [{"type": "record", "data": {"file": "from-req.amr"}}]}
    )

    assert len(VolcengineAsrPlugin._find_records(event)) >= 3

    _ensure_clean_voice_event_for_agent(event)

    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.message_str == "hello"
    assert event.message_obj.message[0].text == "hello"
    provider_request = event.get_extra("provider_request")
    assert provider_request.prompt == "hello"
    assert provider_request.audio_urls == []
    assert provider_request.files == []


def test_agent_begin_cleanup_sanitizes_unknown_extra_cache_keys():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    event.extras["agent_state"] = {
        "payload": {"message": [{"type": "record", "data": {"file": "hidden.amr"}}]}
    }
    event.message_obj.extras["cache"] = {
        "stage_data": [{"type": "record", "data": {"file": "cache.amr"}}],
        "note": "keep me",
    }
    event.extras["plain_state"] = {"message": "keep text", "count": 2}
    event.message_obj.extras["plain_cache"] = {"files": ["report.txt"], "path": "/tmp/report.txt"}

    assert VolcengineAsrPlugin._find_records(event)

    _ensure_clean_voice_event_for_agent(event)

    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.extras["agent_state"]["payload"]["message"][0].text == "hello"
    assert event.message_obj.extras["cache"] == {"stage_data": [], "note": "keep me"}
    assert event.extras["plain_state"] == {"message": "keep text", "count": 2}
    assert event.message_obj.extras["plain_cache"] == {"files": ["report.txt"], "path": "/tmp/report.txt"}


def test_agent_begin_cleanup_preserves_plain_message_when_sibling_audio_removed():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    event.extras["agent_state"] = {
        "message": "keep text",
        "raw_message": "keep raw text",
        "audio_urls": ["hidden.amr"],
    }

    _ensure_clean_voice_event_for_agent(event)

    assert event.extras["agent_state"] == {
        "message": "keep text",
        "raw_message": "keep raw text",
        "audio_urls": [],
    }


def test_agent_begin_cleanup_sanitizes_file_id_record_cache():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    event.extras["agent_state"] = {
        "record": "voice.amr",
        "file_id": "napcat-record-id",
        "file_ids": ["napcat-record-id"],
        "file_name": "voice.amr",
        "filename": "voice.silk",
        "message": "keep text",
    }

    _ensure_clean_voice_event_for_agent(event)

    assert event.extras["agent_state"] == {
        "record": [],
        "file_id": [],
        "file_ids": [],
        "file_name": [],
        "filename": [],
        "message": "keep text",
    }


def test_agent_begin_cleanup_sanitizes_run_context_caches():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    run_context = _FakeRunContext(event=event)

    _ensure_clean_voice_event_for_agent(event, run_context)

    assert run_context.event is event
    assert run_context.provider_request.audio_urls == []
    assert run_context.provider_request.files == []
    assert run_context.provider_request.prompt == "hello[voice prompt]"
    assert run_context.provider_request.cached_content == []
    assert run_context.provider_request.cached_messages == []
    assert run_context.provider_request.history == []
    assert run_context.messages == [{"role": "user", "content": []}]
    assert run_context.stage_data["payload"]["message"][0].text == "hello"
    assert isinstance(run_context.cache["provider_request"], _FakeProviderRequest)
    assert run_context.cache["provider_request"].audio_urls == []
    assert run_context.cache["provider_request"].prompt == "hello[voice prompt]"
    assert run_context.cached_content == []
    assert run_context.cached_messages == []


def test_agent_begin_cleanup_sanitizes_provider_request_alias_extras_without_replacing_objects():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    request = _FakeProviderRequest(prompt="request.amr")
    req = _FakeProviderRequest(prompt="req.amr")
    llm_request = _FakeProviderRequest(prompt="llm-request.amr")
    event.extras["request"] = request
    event.extras["req"] = req
    event.message_obj.extras["llm_request"] = llm_request

    _ensure_clean_voice_event_for_agent(event)

    assert event.extras["request"] is request
    assert event.extras["req"] is req
    assert event.message_obj.extras["llm_request"] is llm_request
    for provider_request in (request, req, llm_request):
        assert provider_request.model_dump_for_context() == {"prompt": "hello[voice prompt]"}
        assert provider_request.audio_urls == []
        assert provider_request.files == []
        assert provider_request.messages == [{"role": "user", "content": [{"type": "text", "text": "old message"}]}]
        assert provider_request.cached_content == []
        assert provider_request.cached_messages == []
        assert provider_request.history == []


def test_agent_begin_cleanup_sanitizes_mapping_run_context_without_replacing_provider_request():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    provider_request = _FakeProviderRequest(prompt="mapping-request.amr")
    run_context = {
        "provider_request": provider_request,
        "messages": [{"role": "user", "content": [{"type": "record", "data": {"file": "mapping-message.amr"}}]}],
        "stage_data": {"payload": {"message": [{"type": "record", "data": {"file": "mapping-stage.amr"}}]}},
        "url": "https://example.com/page.html",
    }

    _ensure_clean_voice_event_for_agent(event, run_context)

    assert run_context["provider_request"] is provider_request
    assert provider_request.model_dump_for_context() == {"prompt": "hello[voice prompt]"}
    assert provider_request.audio_urls == []
    assert provider_request.files == []
    assert run_context["messages"] == [{"role": "user", "content": []}]
    assert run_context["stage_data"]["payload"]["message"][0].text == "hello"
    assert run_context["url"] == "https://example.com/page.html"


def test_agent_begin_cleanup_replaces_inline_audio_references_in_text_caches():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    event.extras["agent_state"] = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请处理 old.amr 后回复"},
                    {"type": "text", "text": "保留普通文字"},
                ],
            }
        ],
        "stage_data": {"payload": {"content": "url https://example.com/voice.wav?token=1 then"}},
        "note": "请解释 amr 格式和 opus 格式的区别",
    }
    run_context = {
        "context": [{"type": "text", "text": r"path=C:\tmp\voice.silk ok"}],
    }

    _ensure_clean_voice_event_for_agent(event, run_context)

    assert event.extras["agent_state"]["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hello[voice prompt]"},
                {"type": "text", "text": "保留普通文字"},
            ],
        }
    ]
    assert event.extras["agent_state"]["stage_data"] == {"payload": {"content": "hello[voice prompt]"}}
    assert event.extras["agent_state"]["note"] == "请解释 amr 格式和 opus 格式的区别"
    assert run_context["context"] == [{"type": "text", "text": "hello[voice prompt]"}]


def test_agent_begin_cleanup_replaces_dict_provider_request_alias_with_clean_request():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    event.extras["provider_request"] = {
        "prompt": "请处理 old.amr 后回复",
        "audio_urls": ["old.amr"],
        "messages": [{"role": "user", "content": [{"type": "record", "data": {"file": "old.amr"}}]}],
    }
    run_context = {
        "request": {
            "prompt": "cached.amr",
            "extra_user_content_parts": [{"type": "audio_url", "audio_url": "cached.amr"}],
        }
    }

    _ensure_clean_voice_event_for_agent(event, run_context)

    provider_request = event.extras["provider_request"]
    cached_request = run_context["request"]
    assert not isinstance(provider_request, dict)
    assert not isinstance(cached_request, dict)
    assert hasattr(provider_request, "prompt")
    assert hasattr(cached_request, "prompt")
    assert provider_request.prompt == "hello[voice prompt]"
    assert cached_request.prompt == "hello[voice prompt]"
    assert provider_request.audio_urls == []
    assert cached_request.audio_urls == []


def test_agent_begin_cleanup_preserves_plain_mapping_values():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    event.extras["plain_state"] = {"url": "https://example.com/page.html", "files": ["report.txt"]}
    event.message_obj.extras["plain_cache"] = {"path": "/tmp/report.txt", "note": "keep me"}

    _ensure_clean_voice_event_for_agent(event)

    assert event.extras["plain_state"] == {"url": "https://example.com/page.html", "files": ["report.txt"]}
    assert event.message_obj.extras["plain_cache"] == {"path": "/tmp/report.txt", "note": "keep me"}


def test_agent_begin_cleanup_preserves_context_only_provider_request_objects():
    event = _FakeEvent()
    event.message = []
    event.message_chain = []
    event.raw_message = []
    event.message_obj.message = []
    event.message_obj.message_chain = []
    event.message_obj.raw_message = []
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "hello")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "hello[voice prompt]")
    request = _ContextOnlyProviderRequest()
    run_context = {"request": request}

    _ensure_clean_voice_event_for_agent(event, run_context)

    assert run_context["request"] is request
    assert request.audio_urls == []
    assert request.files == []
    assert request.messages == [{"role": "user", "content": []}]
    assert request.model_dump_for_context() == {"messages": request.messages}


def test_on_message_success_cleans_extra_cache_shapes_before_agent_stage():
    record = Comp.Record(file="voice.amr")
    event = _FakeEvent([record])
    event.extras["data"] = {"message": [{"type": "record", "data": {"file": "from-data.amr"}}]}
    event.extras["segments"] = [{"type": "record", "data": {"file": "from-segments.amr"}}]
    event.message_obj.extras["original_message"] = [
        {"type": "record", "data": {"file": "from-original.amr"}}
    ]
    event.message_obj.extras["request"] = {
        "messages": [{"content": [{"type": "record", "data": {"file": "from-request.amr"}}]}]
    }
    plugin = _make_plugin()

    async def fake_recognize_voice_inputs(_voice_inputs):
        return RecognitionBatch(results=[AsrResult(text="hello", request_id="req-1")], errors=[])

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs

    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert len(outputs) == 1
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.message_obj.message[0].text == "hello"
    provider_request = event.get_extra("provider_request")
    assert provider_request.prompt == "hello[voice prompt]"
    assert provider_request.audio_urls == []


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


def test_bare_onebot_amr_uses_get_record_then_ffmpeg():
    amr_bytes = b"#!AMR\nvoice"
    record = _OneBotRecord("330898de94fe28ae378bdee1c2fe929f.amr")
    event = _FakeEvent([record])
    event.bot = _FakeOneBot({"file": "base64://" + base64.b64encode(amr_bytes).decode("ascii")})
    plugin = _make_plugin()
    plugin.enable_transcode = True
    plugin.transcode_output_format = "wav"
    seen = {}

    async def fake_transcode_audio(data, suffix):
        seen["data"] = data
        seen["suffix"] = suffix
        return b"RIFFxxxxWAVEfmt "

    plugin._transcode_audio = fake_transcode_audio

    payload = asyncio.run(plugin._build_audio_payload_result(plugin._collect_voice_inputs(event)[0]))

    assert event.bot.calls[0][1]["action"] == "get_record"
    assert event.bot.calls[0][1]["file"] == "330898de94fe28ae378bdee1c2fe929f.amr"
    assert seen == {"data": amr_bytes, "suffix": ".amr"}
    assert payload.source_type == "onebot_get_record"
    assert payload.detected_suffix == ".amr"
    assert payload.transcoded is True
    assert "data" in payload.payload


def test_onebot_get_record_accepts_data_uri_base64_result():
    audio_bytes = b"RIFFxxxxWAVEfmt "
    event = _FakeEvent([])
    plugin = _make_plugin()
    result = {"data": {"base64": "data:audio/wav;base64," + base64.b64encode(audio_bytes).decode("ascii")}}

    loaded = asyncio.run(plugin._load_onebot_record_result(result, "voice.amr"))

    assert loaded == (audio_bytes, "base64://onebot_get_record", "onebot_get_record")


def test_raise_if_content_too_large_ignores_invalid_or_equal_content_length():
    plugin = _make_plugin(max_audio_mb=1)
    response = type("Response", (), {"headers": {"content-length": "not-a-number"}})()

    plugin._raise_if_content_too_large(response)

    response.headers["content-length"] = str(plugin.max_audio_bytes)
    plugin._raise_if_content_too_large(response)

    response.headers["content-length"] = str(plugin.max_audio_bytes + 1)
    try:
        plugin._raise_if_content_too_large(response)
    except UserVisibleError:
        pass
    else:
        raise AssertionError("expected UserVisibleError")


def test_build_audio_payload_reports_user_visible_audio_errors():
    plugin = _make_plugin()
    record = Comp.Record(file="missing.amr")

    async def fake_record_to_audio_bytes(_record, _sources, _event=None):
        raise UserVisibleError("audio unavailable")

    plugin._record_to_audio_bytes = fake_record_to_audio_bytes

    batch = asyncio.run(plugin._recognize_voice_inputs(plugin._collect_voice_inputs(_FakeEvent([record]))))

    assert batch.errors
    assert "audio unavailable" in batch.errors[0]
    assert batch.diagnostics[0]["error_code"] == "audio_prepare_failed"


def test_bare_amr_file_conversion_failure_is_reported_and_stopped():
    record = Comp.Record(file="2f7e2f96f5d363c6311f8bacdaafea11.amr")
    event = _FakeEvent([record])
    plugin = _make_plugin()

    batch = asyncio.run(plugin._recognize_voice_inputs(plugin._collect_voice_inputs(event)))

    assert batch.results == []
    assert batch.diagnostics[0]["error_code"] == "audio_prepare_failed"
    assert "无法从消息中读取语音文件" in batch.errors[0]

    async def fake_recognize_voice_inputs(_voice_inputs):
        return batch

    plugin._recognize_voice_inputs = fake_recognize_voice_inputs
    outputs = asyncio.run(_collect_asyncgen(plugin.on_message(event)))

    assert "无法从消息中读取语音文件" in outputs[0]["text"]
    assert event.stopped == 1
