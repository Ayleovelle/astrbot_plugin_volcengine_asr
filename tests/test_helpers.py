import asyncio
import subprocess
from contextlib import contextmanager

import astrbot_plugin_volcengine_asr.main as plugin_main
from astrbot_plugin_volcengine_asr.main import (
    ASR_EXTRA_INJECTED,
    ASR_EXTRA_LLM_TEXT,
    ASR_EXTRA_MEMORY_TEXT,
    ASR_EXTRA_TEXT,
    ASR_EXTRA_UNCLEAR,
    AsrResult,
    EmotionJudgement,
    UserVisibleError,
    VolcengineAsrPlugin,
    _append_emotion_guidance,
    _build_emotion_judgement,
    _build_emotion_prompt,
    _compute_emotion_respect_weight,
    _detect_audio_suffix,
    _entropy_certainty,
    _estimate_base64_size,
    _extract_record_sources,
    _normalize_emotion_weights,
    _parse_ffmpeg_version_output,
    _probe_ffmpeg_startup,
    _resolve_ffmpeg_path,
    _render_named_placeholders,
    _render_prompt_template,
    _replace_first_text,
    _safe_parse_json_object,
    _sanitize_provider_request,
)
import astrbot.api.message_components as Comp
from scripts.update_fuck_u_code_score import build_svg, extract_score, find_score, normalize_score


@contextmanager
def _patched_attr(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


class _FakeEvent:
    def __init__(self):
        self.extras = {}
        self.message_str = ""
        self.message = []
        self.message_chain = []
        self.raw_message = []
        self.message_obj = type(
            "MessageObj",
            (),
            {
                "message_str": "",
                "message": [],
                "message_chain": [],
                "raw_message": [],
            },
        )()

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_extra(self, key, default=None):
        return self.extras.get(key, default)

    def get_messages(self):
        return self.message_obj.message


class _FakeProviderRequest:
    def __init__(self):
        self.prompt = "干净文本"
        self.audio_urls = ["2f7e2f96f5d363c6311f8bacdaafea11.amr"]
        self.image_urls = []
        self.messages = [
            {
                "role": "user",
                "content": [
                    {"type": "audio_url", "audio_url": "message-hidden.amr"},
                    {"type": "text", "text": "保留 message 文字"},
                ],
            }
        ]
        self.files = ["hidden-file.amr"]
        self.contexts = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "保留这句"},
                    {"type": "audio_url", "audio_url": "2f7e2f96f5d363c6311f8bacdaafea11.amr"},
                ],
            }
        ]
        self.extra_user_content_parts = [
            {"type": "text", "text": "[Audio Attachment: path 2f7e2f96f5d363c6311f8bacdaafea11.amr]"},
            {"type": "text", "text": "保留额外文字"},
        ]


class _AudioPart:
    type = "audio_url"

    def __init__(self, audio_url):
        self.audio_url = audio_url


class _TextPart:
    type = "text"

    def __init__(self, text):
        self.text = text


class _CompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_render_prompt_template_supports_angle_placeholder_with_braces_text():
    rendered = _render_prompt_template(
        "<text>[请自然回复]",
        {"text": "今天聊 {AI} 可以吗", "logid": "log-1", "request_id": "req-1", "duration_ms": 123},
    )

    assert rendered == "今天聊 {AI} 可以吗[请自然回复]"


def test_render_prompt_template_supports_format_fields():
    rendered = _render_prompt_template(
        "语音：{text} logid={logid} request={request_id} duration={duration_ms}",
        {"text": "你好", "logid": "log-1", "request_id": "req-1", "duration_ms": 123},
    )

    assert rendered == "语音：你好 logid=log-1 request=req-1 duration=123"


def test_render_prompt_template_supports_angle_placeholder_with_other_fields():
    rendered = _render_prompt_template(
        "<text> logid={logid}",
        {"text": "你好", "logid": "log-1", "request_id": "req-1", "duration_ms": ""},
    )

    assert rendered == "你好 logid=log-1"


def test_replace_first_text_only_replaces_first_match():
    text, replaced = _replace_first_text("hello hello", "hello", "voice")

    assert replaced is True
    assert text == "voice hello"


def test_detect_audio_suffix_uses_magic_headers():
    assert _detect_audio_suffix(b"RIFFxxxxWAVEfmt", "voice.bin") == ".wav"
    assert _detect_audio_suffix(b"OggSxxxx", "voice.bin") == ".ogg"
    assert _detect_audio_suffix(b"ID3xxxx", "voice.bin") == ".mp3"
    assert _detect_audio_suffix(b"#!AMR\n", "voice.bin") == ".amr"
    assert _detect_audio_suffix(b"#!SILK_V3", "voice.bin") == ".silk"


def test_parse_ffmpeg_version_output_reads_first_line_version():
    assert _parse_ffmpeg_version_output("ffmpeg version 6.1.1 Copyright ...") == "6.1.1"
    assert _parse_ffmpeg_version_output("not ffmpeg") is None


def test_probe_ffmpeg_startup_success_and_permission_failure():
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return _CompletedProcess(
            returncode=0,
            stdout="ffmpeg version 6.1.1 Copyright ...",
        )

    with _patched_attr(plugin_main.subprocess, "run", fake_run):
        ok, detail = _probe_ffmpeg_startup("/tmp/ffmpeg")

    assert ok is True
    assert detail == "6.1.1"
    assert calls[0][0] == ["/tmp/ffmpeg", "-version"]
    assert calls[0][1]["timeout"] == plugin_main.FFMPEG_PROBE_TIMEOUT_SECONDS

    def fake_permission_error(command, **kwargs):
        raise PermissionError("denied")

    with _patched_attr(plugin_main.subprocess, "run", fake_permission_error):
        ok, detail = _probe_ffmpeg_startup("/tmp/ffmpeg")

    assert ok is False
    assert "执行权限" in detail


def test_probe_ffmpeg_startup_rejects_bad_version_output():
    def fake_run(command, **kwargs):
        return _CompletedProcess(returncode=0, stdout="hello")

    with _patched_attr(plugin_main.subprocess, "run", fake_run):
        ok, detail = _probe_ffmpeg_startup("/tmp/ffmpeg")

    assert ok is False
    assert "无法识别" in detail


def test_resolve_ffmpeg_path_falls_back_after_failed_candidates():
    calls = []

    def fake_probe(path):
        calls.append(path)
        return (path == "ffmpeg", "7.0" if path == "ffmpeg" else "没有执行权限")

    with _patched_attr(plugin_main, "_probe_ffmpeg_startup", fake_probe):
        path, source, error = _resolve_ffmpeg_path("auto", prefer_bundled=False)

    assert path == "ffmpeg"
    assert source == "PATH (7.0)"
    assert error == ""
    assert calls == ["ffmpeg"]


def test_resolve_ffmpeg_path_keeps_diagnostic_when_all_candidates_fail():
    def fake_probe(path):
        return False, "没有执行权限"

    with _patched_attr(plugin_main, "_probe_ffmpeg_startup", fake_probe):
        path, source, error = _resolve_ffmpeg_path("/bad/ffmpeg", prefer_bundled=True)

    assert path == "/bad/ffmpeg"
    assert source == "不可用"
    assert "未找到可启动的 ffmpeg" in error
    assert "/bad/ffmpeg" in error


def test_estimate_base64_size_handles_padding():
    assert _estimate_base64_size("TQ==") == 1
    assert _estimate_base64_size("TWE=") == 2
    assert _estimate_base64_size("TWFu") == 3


def test_extract_record_sources_supports_object_dict_and_nested_data():
    record = Comp.Record(file="voice.amr", url="https://example.com/voice.amr")
    nested_object = Comp.Record(data={"path": "/tmp/voice.silk", "file": "nested.amr"})
    nested_dict = {
        "type": "record",
        "data": {"url": "https://example.com/nested.amr", "file": "fallback.amr"},
    }

    assert _extract_record_sources(record) == [
        "voice.amr",
        "https://example.com/voice.amr",
    ]
    assert _extract_record_sources(nested_object) == ["/tmp/voice.silk", "nested.amr"]
    assert _extract_record_sources(nested_dict) == [
        "fallback.amr",
        "https://example.com/nested.amr",
    ]


def test_find_records_reads_compatible_message_chains():
    event = _FakeEvent()
    main_record = Comp.Record(file="message.amr")
    obj_chain_record = Comp.Record(file="message-chain.amr")
    event_chain_record = Comp.Record(file="event-chain.amr")
    raw_nested_record = {"type": "record", "data": {"file": "raw-nested.amr"}}
    raw_dict_record = {"type": "record", "data": {"file": "raw.amr"}}

    event.message_obj.message = [main_record]
    event.message_obj.message_chain = [obj_chain_record]
    event.message_chain = [event_chain_record]
    event.raw_message = {"message": [raw_nested_record], "raw_message": [raw_dict_record]}

    records = VolcengineAsrPlugin._find_records(event)

    assert records == [
        main_record,
        obj_chain_record,
        event_chain_record,
        raw_nested_record,
        raw_dict_record,
    ]


def test_find_records_reads_bare_raw_record_dict():
    event = _FakeEvent()
    raw_record = {"type": "record", "data": {"file": "raw.amr"}}
    event.raw_message = raw_record

    assert VolcengineAsrPlugin._find_records(event) == [raw_record]


def test_safe_parse_json_object_handles_raw_and_fenced_json():
    assert _safe_parse_json_object('{"label":"neutral"}') == {"label": "neutral"}
    assert _safe_parse_json_object('```json\n{"label":"happy"}\n```') == {"label": "happy"}
    assert _safe_parse_json_object('prefix {"label":"sad"} suffix') == {"label": "sad"}
    assert _safe_parse_json_object('not json') is None


def test_normalize_emotion_weights_clamps_and_normalizes():
    weights = _normalize_emotion_weights({"happy": 0.8, "sad": 0.2, "bad": 1, "angry": -1})

    assert set(weights) == {"happy", "sad"}
    assert round(sum(weights.values()), 6) == 1
    assert weights["happy"] > weights["sad"]


def test_entropy_certainty_reflects_distribution_confidence():
    assert _entropy_certainty({"happy": 1.0}) == 1.0
    assert _entropy_certainty({"happy": 0.9, "sad": 0.1}) > _entropy_certainty(
        {"happy": 0.5, "sad": 0.5}
    )


def test_compute_emotion_respect_weight_uses_confidence_certainty_and_caps_short_text():
    high = _compute_emotion_respect_weight(
        transcript_chars=80,
        confidence=0.9,
        emotion_weights={"anxious": 0.9, "sad": 0.1},
        voice_text_support=0.9,
        context_support=0.6,
        max_respect_weight=0.6,
    )
    low = _compute_emotion_respect_weight(
        transcript_chars=80,
        confidence=0.2,
        emotion_weights={"anxious": 0.5, "sad": 0.5},
        voice_text_support=0.1,
        context_support=0.1,
        max_respect_weight=0.6,
    )
    short = _compute_emotion_respect_weight(
        transcript_chars=3,
        confidence=1,
        emotion_weights={"anxious": 1},
        voice_text_support=1,
        context_support=1,
        max_respect_weight=0.6,
    )

    assert high > low
    assert high <= 0.6
    assert short <= 0.25


def test_build_emotion_judgement_uses_local_respect_weight_formula():
    judgement = _build_emotion_judgement(
        {
            "label": "anxious",
            "emotion_weights": {"anxious": 0.8, "sad": 0.2},
            "confidence": 0.7,
            "valence": -0.4,
            "arousal": 0.6,
            "voice_text_support": 0.8,
            "context_support": 0.3,
            "reason": "用户表达担心。\n额外内容会被压平。",
        },
        transcript_chars=30,
        max_respect_weight=0.6,
    )

    assert judgement.label == "anxious"
    assert 0 < judgement.respect_weight <= 0.6
    assert "\n" not in judgement.reason


def test_build_emotion_prompt_preserves_json_braces():
    prompt = _build_emotion_prompt(
        '输出 JSON：{"label":"neutral"} text={text} context={context}',
        transcription_text="你好 {AI}",
        context_text="上文",
    )

    assert '{"label":"neutral"}' in prompt
    assert "你好 {AI}" in prompt
    assert "上文" in prompt


def test_render_named_placeholders_only_replaces_named_fields():
    rendered = _render_named_placeholders(
        '{"label":"neutral"} {text} {context} {unknown}',
        {"text": "你好 {context}", "context": "上文"},
    )

    assert rendered == '{"label":"neutral"} 你好 {context} 上文 {unknown}'


def test_append_emotion_guidance_only_changes_llm_text():
    judgement = EmotionJudgement(
        label="anxious",
        emotion_weights={"anxious": 0.8, "neutral": 0.2},
        confidence=0.7,
        respect_weight=0.4,
        valence=-0.3,
        arousal=0.6,
        voice_text_support=0.8,
        context_support=0.2,
        reason="用户表达担心。",
    )

    result = _append_emotion_guidance("原始 LLM 文本", judgement)

    assert result.startswith("原始 LLM 文本")
    assert "情绪判断辅助信息" in result
    assert "建议参考权重：0.40" in result
    assert _append_emotion_guidance("原始 LLM 文本", None) == "原始 LLM 文本"


def test_build_result_values_reuses_transcription_formatting():
    plugin = VolcengineAsrPlugin(None, {"api_key": "token"})
    results = [
        AsrResult(text="你好", request_id="req-1", logid="log-1", duration_ms=100),
        AsrResult(text="世界", request_id="req-2", logid="", duration_ms=200),
    ]

    values = plugin._build_result_values(results)

    assert values["text"] == "1. 你好\n2. 世界"
    assert values["logid"] == "log-1"
    assert values["request_id"] == "req-1,req-2"
    assert values["duration_ms"] == ""


def test_inject_user_text_sets_clean_message_and_asr_extras():
    event = _FakeEvent()
    record = Comp.Record(file="d288c78e8c3716a65e75983adcdd4a5a.amr")
    raw_record = {"type": "record", "data": {"file": "raw.amr"}}
    old_message = [record]
    old_message_chain = [record]
    old_obj_message = [record]
    old_obj_message_chain = [record]
    event.message = old_message
    event.message_chain = old_message_chain
    event.raw_message = [raw_record]
    event.message_obj.message = old_obj_message
    event.message_obj.message_chain = old_obj_message_chain
    event.message_obj.raw_message = [raw_record]

    VolcengineAsrPlugin._inject_user_text(
        event,
        memory_text="干净文本",
        llm_text="LLM 文本",
        raw_text="原始文本",
        unclear=True,
    )

    assert event.message_str == "干净文本"
    assert event.message[0].text == "干净文本"
    assert event.message_chain[0].text == "干净文本"
    assert event.raw_message == "干净文本"
    assert event.message_obj.message_str == "干净文本"
    assert event.message_obj.message[0].text == "干净文本"
    assert event.message_obj.message_chain[0].text == "干净文本"
    assert event.message_obj.raw_message == "干净文本"
    assert old_message[0].text == "干净文本"
    assert old_message_chain[0].text == "干净文本"
    assert old_obj_message[0].text == "干净文本"
    assert old_obj_message_chain[0].text == "干净文本"
    assert VolcengineAsrPlugin._find_records(event) == []
    assert event.extras[ASR_EXTRA_TEXT] == "原始文本"
    assert event.extras[ASR_EXTRA_MEMORY_TEXT] == "干净文本"
    assert event.extras[ASR_EXTRA_LLM_TEXT] == "LLM 文本"
    assert event.extras[ASR_EXTRA_INJECTED] is True
    assert event.extras[ASR_EXTRA_UNCLEAR] is True


def test_inject_user_text_sanitizes_cached_extra_records():
    event = _FakeEvent()
    event.extras["raw_message"] = [
        {"type": "record", "data": {"file": "2f7e2f96f5d363c6311f8bacdaafea11.amr"}}
    ]
    event.extras["audio_urls"] = ["2f7e2f96f5d363c6311f8bacdaafea11.amr"]
    event.message_obj.extras = {
        "contexts": [{"role": "user", "content": [{"type": "audio_url", "audio_url": "cached.amr"}]}],
        "records": [Comp.Record(file="cached-record.amr")],
    }

    VolcengineAsrPlugin._inject_user_text(
        event,
        memory_text="干净文本",
        llm_text="LLM 文本",
        raw_text="原始文本",
    )

    assert event.extras["raw_message"] == []
    assert event.extras["audio_urls"] == []
    assert event.message_obj.extras["contexts"] == [{"role": "user", "content": []}]
    assert event.message_obj.extras["records"] == []
    assert event.extras[ASR_EXTRA_MEMORY_TEXT] == "干净文本"


def test_sanitize_provider_request_removes_audio_inputs_and_preserves_text():
    req = _FakeProviderRequest()

    _sanitize_provider_request(req, "干净文本", "LLM 文本")

    assert req.audio_urls == []
    assert req.contexts == [{"role": "user", "content": [{"type": "text", "text": "保留这句"}]}]
    assert req.extra_user_content_parts == [{"type": "text", "text": "保留额外文字"}]
    assert req.messages == [{"role": "user", "content": [{"type": "text", "text": "保留 message 文字"}]}]
    assert req.files == []


def test_sanitize_provider_request_removes_object_audio_parts():
    req = _FakeProviderRequest()
    req.extra_user_content_parts = [
        _AudioPart("object-audio.amr"),
        _TextPart("保留对象文字"),
    ]

    _sanitize_provider_request(req, "干净文本", "LLM 文本")

    assert req.extra_user_content_parts == [{"type": "text", "text": "保留对象文字"}]


def test_apply_voice_prompt_template_sanitizes_provider_request_audio_inputs():
    plugin = VolcengineAsrPlugin(None, {"api_key": "token"})
    event = _FakeEvent()
    req = _FakeProviderRequest()
    event.set_extra(ASR_EXTRA_MEMORY_TEXT, "干净文本")
    event.set_extra(ASR_EXTRA_LLM_TEXT, "LLM 文本")
    event.set_extra(ASR_EXTRA_INJECTED, True)

    coro = plugin.apply_voice_prompt_template(event, req)
    try:
        coro.send(None)
    except StopIteration:
        pass

    assert req.prompt == "LLM 文本"
    assert req.audio_urls == []
    assert req.contexts == [{"role": "user", "content": [{"type": "text", "text": "保留这句"}]}]
    assert req.extra_user_content_parts == [{"type": "text", "text": "保留额外文字"}]
    assert req.messages == [{"role": "user", "content": [{"type": "text", "text": "保留 message 文字"}]}]
    assert req.files == []
    assert event.get_extra("volcengine_asr_llm_prompt_applied") is True


def test_webui_snapshot_exposes_stable_state_schema_and_config_values():
    plugin = VolcengineAsrPlugin(
        None,
        {
            "api_key": "token",
            "submit_mode": "base64",
            "enable_emotion_analysis": True,
            "emotion_model_id": "emotion-provider",
            "emotion_max_respect_weight_percent": 40,
        },
    )

    state = plugin.get_webui_state()
    schema = plugin.get_webui_config_schema()
    snapshot = plugin.get_webui_config_snapshot()

    assert state["auth_configured"] is True
    assert state["schema_version"] == 1
    assert state["submit_mode"] == "base64"
    assert state["emotion"]["enabled"] is True
    assert state["emotion"]["model_id"] == "emotion-provider"
    assert state["emotion"]["max_respect_weight_percent"] == 40
    assert "api_key" in schema
    assert snapshot["api_key"] == "****"
    assert "access_key" in snapshot


def test_webui_update_skips_unchanged_masked_secret_and_reloads_runtime_values():
    plugin = VolcengineAsrPlugin(
        None,
        {
            "api_key": "abcd1234wxyz",
            "submit_mode": "base64",
            "max_audio_mb": 20,
            "enable_emotion_analysis": False,
        },
    )
    snapshot = plugin.get_webui_config_snapshot()

    result = plugin.update_webui_config(
        {
            "api_key": snapshot["api_key"],
            "submit_mode": "URL",
            "max_audio_mb": "12",
            "enable_emotion_analysis": "true",
        }
    )

    assert result["errors"] == {}
    assert result["skipped"]["api_key"] == "密钥未变更"
    assert "api_key" not in result["applied"]
    assert plugin.config["api_key"] == "abcd1234wxyz"
    assert plugin.submit_mode == "url"
    assert plugin.max_audio_bytes == 12 * 1024 * 1024
    assert plugin.enable_emotion_analysis is True
    assert plugin.get_webui_state()["max_audio_mb"] == 12


def test_webui_update_validates_type_options_and_ranges():
    plugin = VolcengineAsrPlugin(None, {"api_key": "token"})

    result = plugin.update_webui_config(
        {
            "submit_mode": "bad",
            "max_audio_mb": "abc",
            "enable_group": 1,
            "emotion_max_respect_weight_percent": 101,
            "unknown_key": "value",
        }
    )

    assert "submit_mode" in result["errors"]
    assert "max_audio_mb" in result["errors"]
    assert "enable_group" in result["errors"]
    assert "emotion_max_respect_weight_percent" in result["errors"]
    assert result["skipped"]["unknown_key"] == "未知配置项"
    assert result["applied"] == {}
    assert plugin.submit_mode == "base64"


def test_runtime_config_skips_ffmpeg_probe_when_transcode_disabled():
    def fake_probe(path):
        raise AssertionError("ffmpeg should not be probed when transcode is disabled")

    with _patched_attr(plugin_main, "_probe_ffmpeg_startup", fake_probe):
        plugin = VolcengineAsrPlugin(
            None,
            {"api_key": "token", "enable_transcode": False, "ffmpeg_path": "auto"},
        )

    state = plugin.get_webui_state()
    assert state["enable_transcode"] is False
    assert state["ffmpeg_source"] == "未探测（自动转码关闭）"
    assert state["ffmpeg_status"] == "未探测（自动转码关闭）"


def test_transcode_audio_wraps_ffmpeg_startup_os_errors():
    plugin = VolcengineAsrPlugin(None, {"api_key": "token", "ffmpeg_path": "ffmpeg", "prefer_bundled_ffmpeg": False})
    plugin.ffmpeg_error = ""
    plugin.ffmpeg_path = "/tmp/ffmpeg"

    async def fake_create_subprocess_exec(*args, **kwargs):
        raise PermissionError("denied")

    with _patched_attr(plugin_main.asyncio, "create_subprocess_exec", fake_create_subprocess_exec):
        try:
            asyncio.run(plugin._transcode_audio(b"abc", ".amr"))
        except UserVisibleError as exc:
            assert "ffmpeg 启动失败" in str(exc)
            assert "ffmpeg_path" in str(exc)
        else:
            raise AssertionError("expected UserVisibleError")


def test_transcode_audio_uses_cached_ffmpeg_probe_error_before_spawn():
    plugin = VolcengineAsrPlugin(None, {"api_key": "token", "ffmpeg_path": "ffmpeg", "prefer_bundled_ffmpeg": False})
    plugin.ffmpeg_error = "未找到可启动的 ffmpeg"

    async def fake_create_subprocess_exec(*args, **kwargs):
        raise AssertionError("ffmpeg should not spawn when probe failed")

    with _patched_attr(plugin_main.asyncio, "create_subprocess_exec", fake_create_subprocess_exec):
        try:
            asyncio.run(plugin._transcode_audio(b"abc", ".amr"))
        except UserVisibleError as exc:
            assert "未找到可启动的 ffmpeg" in str(exc)
        else:
            raise AssertionError("expected UserVisibleError")


def test_extract_fuck_u_code_score_from_report_text():
    report = """
    # fuck-u-code report

    总分：68.391
    """

    assert extract_score(report) == "68.39"


def test_find_fuck_u_code_score_returns_none_without_score():
    assert find_score("# report\nno numeric score here") is None


def test_normalize_fuck_u_code_score_clamps_range():
    assert normalize_score("-1") == "0.00"
    assert normalize_score("102") == "100.00"
    assert normalize_score("7") == "7.00"


def test_build_fuck_u_code_svg_contains_score_and_bot_description():
    svg = build_svg("68.39")

    assert 'width="250"' in svg
    assert 'height="54"' in svg
    assert "github Actions bot" not in svg
    assert "GitHub Actions bot" in svg
    assert ">68.39<" in svg
