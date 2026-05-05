from astrbot_plugin_volcengine_asr.main import (
    _detect_audio_suffix,
    _estimate_base64_size,
    _render_prompt_template,
    _replace_first_text,
)


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


def test_estimate_base64_size_handles_padding():
    assert _estimate_base64_size("TQ==") == 1
    assert _estimate_base64_size("TWE=") == 2
    assert _estimate_base64_size("TWFu") == 3
