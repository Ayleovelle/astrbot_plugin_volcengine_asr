from astrbot_plugin_volcengine_asr.main import (
    EmotionJudgement,
    _append_emotion_guidance,
    _build_emotion_judgement,
    _build_emotion_prompt,
    _compute_emotion_respect_weight,
    _detect_audio_suffix,
    _entropy_certainty,
    _estimate_base64_size,
    _normalize_emotion_weights,
    _render_named_placeholders,
    _render_prompt_template,
    _replace_first_text,
    _safe_parse_json_object,
)
from scripts.update_fuck_u_code_score import build_svg, extract_score, find_score, normalize_score


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
