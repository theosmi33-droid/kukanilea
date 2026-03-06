from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import unquote


Decision = str


@dataclass(frozen=True)
class GuardrailAssessment:
    decision: Decision
    risk_score: int
    reasons: tuple[str, ...]
    matched_signals: tuple[str, ...]
    normalized_text: str


_OVERRIDE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("instruction_override", re.compile(r"(?i)\bignore\s+(?:all\s+|previous\s+)?instructions?\b")),
    ("instruction_override", re.compile(r"(?i)\b(?:override|disregard)\s+(?:policy|guardrails?|rules?)\b")),
    ("role_confusion", re.compile(r"(?i)\byou\s+are\s+now\s+(?:system|developer|admin|root|dan)\b")),
    ("tool_escalation", re.compile(r"(?i)\b(?:run|execute|call|use)\s+(?:shell|terminal|subprocess|tool)\b")),
    ("exfiltration", re.compile(r"(?i)\b(?:send|upload|post|exfiltrat\w*)\b.{0,40}\b(?:extern(?:al|ally)|remote|http|https|ftp|webhook)\b")),
    ("destructive_request", re.compile(r"(?i)\b(?:delete|wipe|destroy|drop|purge)\b.{0,30}\b(?:all|backup|database|logs|files?)\b")),
    ("credential_rotation", re.compile(r"(?i)\b(?:rotate|reset|revoke)\b.{0,20}\b(?:key|token|credential|password)\b")),
    ("filesystem_network", re.compile(r"(?i)\b(?:/etc/passwd|\.ssh|id_rsa|curl\s+https?://|wget\s+https?://|scp\s+)\b")),
    ("prompt_leak", re.compile(r"(?i)\b(?:reveal|print|dump)\b.{0,40}\b(?:system\s+prompt|hidden\s+instructions?)\b")),
    ("hidden_directive", re.compile(r"(?is)```(?:prompt|system|instructions)[^`]*```")),
    ("hidden_directive", re.compile(r"(?i)(?:^|\n)\s*>\s*system\s*:\s*")),
)

_LOW_RISK_WARN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("quoted_attack_example", re.compile(r"(?i)\bexample\b.*\bignore previous instructions\b")),
    ("quoted_attack_example", re.compile(r"(?i)\bprompt\s*injection\b")),
)


def _normalize(text: str) -> str:
    raw = str(text or "")
    variants = [raw, unescape(raw), unquote(raw), unescape(unquote(raw))]

    compact = re.sub(r"\s+", " ", raw).strip()
    variants.append(compact)

    # Best-effort decode for simple base64-encoded prompt-injection snippets.
    b64_candidate = re.sub(r"\s+", "", raw)
    if len(b64_candidate) >= 16 and re.fullmatch(r"[A-Za-z0-9+/=]+", b64_candidate or ""):
        try:
            decoded = base64.b64decode(b64_candidate, validate=True)
            variants.append(decoded.decode("utf-8", errors="ignore"))
        except (binascii.Error, ValueError):
            pass

    return "\n".join(v for v in variants if v)


def assess_untrusted_input(text: str) -> GuardrailAssessment:
    normalized = _normalize(text)
    matched: list[str] = []
    reasons: list[str] = []
    score = 0

    for signal, pattern in _OVERRIDE_PATTERNS:
        if pattern.search(normalized):
            matched.append(signal)
            score += 28 if signal in {"destructive_request", "exfiltration", "filesystem_network"} else 22

    for signal, pattern in _LOW_RISK_WARN_PATTERNS:
        if pattern.search(normalized):
            matched.append(signal)
            score += 8

    uniq = tuple(sorted(set(matched)))

    if not uniq:
        decision: Decision = "allow"
        reasons.append("no_high_risk_signals")
    elif any(s in uniq for s in ("destructive_request", "exfiltration", "filesystem_network")):
        decision = "block"
        reasons.append("high_risk_execution_or_exfiltration_signal")
    elif any(s in uniq for s in ("instruction_override", "tool_escalation", "role_confusion", "prompt_leak", "hidden_directive", "credential_rotation")):
        decision = "route_to_review"
        reasons.append("possible_prompt_or_policy_manipulation")
    else:
        decision = "allow_with_warning"
        reasons.append("suspicious_but_context_may_be_benign")

    return GuardrailAssessment(
        decision=decision,
        risk_score=min(score, 100),
        reasons=tuple(reasons),
        matched_signals=uniq,
        normalized_text=normalized[:4000],
    )
