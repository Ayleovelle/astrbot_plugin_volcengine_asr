from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


TOKEN_RISK_MEDIUM_TOKENS_DEFAULT = 8000
TOKEN_RISK_HIGH_TOKENS_DEFAULT = 24000
TOKEN_RISK_CRITICAL_TOKENS_DEFAULT = 64000


def estimate_text_tokens(text: str) -> int:
    """Cheap mixed Chinese/English token estimate for local risk gating."""
    if not text:
        return 0
    tokens = 0
    ascii_run = 0
    for char in text:
        codepoint = ord(char)
        if char.isspace():
            if ascii_run:
                tokens += max(1, math.ceil(ascii_run / 4))
                ascii_run = 0
            continue
        if codepoint < 128:
            ascii_run += 1
            continue
        if ascii_run:
            tokens += max(1, math.ceil(ascii_run / 4))
            ascii_run = 0
        if "\u4e00" <= char <= "\u9fff":
            tokens += 1
        else:
            tokens += 2 if len(char.encode("utf-8", errors="ignore")) >= 4 else 1
    if ascii_run:
        tokens += max(1, math.ceil(ascii_run / 4))
    return max(1, tokens)


def compact_text_for_prompt(text: str, max_chars: int) -> str:
    value = " ".join(str(text or "").split())
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    half = max(0, (max_chars - 16) // 2)
    if half <= 0:
        return value[:max_chars]
    return f"{value[:half].rstrip()} ... {value[-half:].lstrip()}"


@dataclass(slots=True)
class TokenRiskAssessment:
    estimated_prompt_tokens: int
    level: str
    action: str
    reason: str
    prompt_chars: int
    context_chars: int
    transcription_chars: int
    final_prompt_tokens: int | None = None
    final_prompt_chars: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_prompt_tokens": self.estimated_prompt_tokens,
            "level": self.level,
            "action": self.action,
            "reason": self.reason,
            "prompt_chars": self.prompt_chars,
            "context_chars": self.context_chars,
            "transcription_chars": self.transcription_chars,
            "final_prompt_tokens": self.final_prompt_tokens,
            "final_prompt_chars": self.final_prompt_chars,
        }

    def with_final_prompt(self, prompt: str) -> "TokenRiskAssessment":
        return TokenRiskAssessment(
            estimated_prompt_tokens=self.estimated_prompt_tokens,
            level=self.level,
            action=self.action,
            reason=self.reason,
            prompt_chars=self.prompt_chars,
            context_chars=self.context_chars,
            transcription_chars=self.transcription_chars,
            final_prompt_tokens=estimate_text_tokens(prompt),
            final_prompt_chars=len(prompt or ""),
        )


@dataclass(slots=True)
class TokenRiskPolicy:
    enabled: bool = True
    medium_tokens: int = TOKEN_RISK_MEDIUM_TOKENS_DEFAULT
    high_tokens: int = TOKEN_RISK_HIGH_TOKENS_DEFAULT
    critical_tokens: int = TOKEN_RISK_CRITICAL_TOKENS_DEFAULT

    def assess(
        self,
        prompt: str,
        *,
        context_text: str = "",
        transcription_text: str = "",
    ) -> TokenRiskAssessment:
        estimated = estimate_text_tokens(prompt)
        medium = max(1, self.medium_tokens)
        high = max(medium, self.high_tokens)
        critical = max(high, self.critical_tokens)
        if not self.enabled:
            level = "off"
            action = "full"
            reason = "token 风险保护未启用。"
        elif estimated >= critical:
            level = "critical"
            action = "skip_llm_injection"
            reason = "估算 prompt token 已达到 critical 阈值，跳过 LLM 注入以避免上游空回复或高额消耗。"
        elif estimated >= high:
            level = "high"
            action = "compact_voice_prompt"
            reason = "估算 prompt token 较高，使用压缩语音提示。"
        elif estimated >= medium:
            level = "medium"
            action = "compact_emotion_guidance"
            reason = "估算 prompt token 进入中风险区间，压缩情绪辅助信息。"
        else:
            level = "low"
            action = "full"
            reason = "估算 token 位于低风险区间。"
        return TokenRiskAssessment(
            estimated_prompt_tokens=estimated,
            level=level,
            action=action,
            reason=reason,
            prompt_chars=len(prompt or ""),
            context_chars=len(context_text or ""),
            transcription_chars=len(transcription_text or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "medium_tokens": self.medium_tokens,
            "high_tokens": self.high_tokens,
            "critical_tokens": self.critical_tokens,
        }
