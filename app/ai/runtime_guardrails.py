from __future__ import annotations

import re
from dataclasses import dataclass

from app.security.untrusted_input import GuardrailAssessment, assess_untrusted_input

GuardrailDecision = str
GuardrailStage = str

UNTRUSTED_INPUT_SOURCES = frozenset({"email", "ocr", "messenger", "markdown", "logs", "other"})

_SHELL_EXECUTION_PATTERN = re.compile(
    r"(?i)\b(?:bash|sh|zsh|powershell|pwsh|cmd\.exe|subprocess|os\.system|xp_cmdshell)\b|(?:\|\s*sh\b)"
)
_BENIGN_CONTEXT_PATTERN = re.compile(
    r"(?i)\b(?:example|beispiel|training|schulung|audit|bericht|log(?:s)?|dokumentation|analyse|markdown)\b"
)
_IMPERATIVE_PATTERN = re.compile(
    r"(?i)\b(?:run|execute|delete|drop|wipe|send|upload|reveal|print|show|do|mach|führe|loesche|lösche|sende|zeige)\b"
)
_POLICY_BYPASS_PATTERN = re.compile(r"(?i)\b(?:bypass|disable)\b.{0,20}\b(?:security|guardrails?|safety)\b")
_PROMPT_LEAK_PATTERN = re.compile(r"(?i)\b(?:show|reveal|print|dump)\b.{0,30}\b(?:system\s+prompt|hidden\s+instructions?)\b")
_NON_DOWNGRADABLE_SIGNALS = frozenset(
    {
        "instruction_override",
        "tool_escalation",
        "role_confusion",
        "prompt_leak",
        "hidden_directive",
        "credential_rotation",
    }
)
_NON_DOWNGRADABLE_REASONS = frozenset(
    {
        "uncontrolled_tool_selection",
        "no_policy_bypass",
        "prompt_leak_request",
        "no_free_shell_execution",
        "shell_skill_blocked",
    }
)


@dataclass(frozen=True)
class RuntimeGuardrailResult:
    decision: GuardrailDecision
    stage: GuardrailStage
    source: str
    risk_score: int
    reasons: tuple[str, ...]
    matched_signals: tuple[str, ...]
    warnings: tuple[str, ...] = ()



def _enforce_no_free_shell(text: str, reasons: list[str]) -> bool:
    if _SHELL_EXECUTION_PATTERN.search(text):
        reasons.append("no_free_shell_execution")
        return True
    return False



def _is_benign_security_discussion(text: str, assessment: GuardrailAssessment) -> bool:
    if not assessment.matched_signals:
        return False
    if any(s in _NON_DOWNGRADABLE_SIGNALS for s in assessment.matched_signals):
        return False
    high_risk = {"destructive_request", "exfiltration", "filesystem_network"}
    if any(s in high_risk for s in assessment.matched_signals):
        return False
    return bool(_BENIGN_CONTEXT_PATTERN.search(text) and not _IMPERATIVE_PATTERN.search(text))



def evaluate_runtime_guardrails(
    *,
    stage: GuardrailStage,
    text: str,
    source: str = "chat",
    skill_name: str | None = None,
    allowed_skills: set[str] | None = None,
) -> RuntimeGuardrailResult:
    normalized_source = str(source or "other").strip().lower() or "other"
    assessment = assess_untrusted_input(text)
    reasons = list(assessment.reasons)
    warnings: list[str] = []
    decision = assessment.decision

    if _enforce_no_free_shell(assessment.normalized_text, reasons):
        decision = "block"

    bypass_signals = {"instruction_override", "tool_escalation", "role_confusion", "prompt_leak", "hidden_directive"}
    if decision == "allow" and any(sig in bypass_signals for sig in assessment.matched_signals):
        decision = "route_to_review"
        reasons.append("no_policy_bypass")

    if decision == "allow" and _POLICY_BYPASS_PATTERN.search(assessment.normalized_text):
        decision = "route_to_review"
        reasons.append("no_policy_bypass")

    if decision == "allow" and _PROMPT_LEAK_PATTERN.search(assessment.normalized_text):
        decision = "route_to_review"
        reasons.append("prompt_leak_request")

    if normalized_source in UNTRUSTED_INPUT_SOURCES and decision == "allow":
        warnings.append("untrusted_input_source")

    if stage == "execution":
        normalized_skill = str(skill_name or "").strip().lower()
        if normalized_skill and _SHELL_EXECUTION_PATTERN.search(normalized_skill):
            decision = "block"
            reasons.append("shell_skill_blocked")
        if allowed_skills and normalized_skill and normalized_skill not in allowed_skills:
            if decision != "block":
                decision = "route_to_review"
            reasons.append("uncontrolled_tool_selection")

    if (
        decision == "route_to_review"
        and not any(reason in _NON_DOWNGRADABLE_REASONS for reason in reasons)
        and _is_benign_security_discussion(assessment.normalized_text, assessment)
    ):
        decision = "allow_with_warning"
        reasons.append("benign_security_discussion")

    if decision == "allow_with_warning" and "guardrail_warning" not in warnings:
        warnings.append("guardrail_warning")

    return RuntimeGuardrailResult(
        decision=decision,
        stage=stage,
        source=normalized_source,
        risk_score=assessment.risk_score,
        reasons=tuple(dict.fromkeys(reasons)),
        matched_signals=assessment.matched_signals,
        warnings=tuple(dict.fromkeys(warnings)),
    )
