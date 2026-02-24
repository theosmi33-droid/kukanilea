from __future__ import annotations

import re
from typing import Any

LABELS = ("lead", "support", "invoice", "appointment", "unknown")
PRIORITIES = ("low", "normal", "high")

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "invoice": (
        "rechnung",
        "invoice",
        "mahnung",
        "zahlung",
        "abschlag",
        "gutschrift",
    ),
    "appointment": (
        "termin",
        "appointment",
        "meeting",
        "besichtigung",
        "vor ort",
        "vor-ort",
    ),
    "support": (
        "störung",
        "stoerung",
        "fehler",
        "defekt",
        "hilfe",
        "support",
        "problem",
    ),
    "lead": (
        "angebot",
        "anfrage",
        "interesse",
        "neukunde",
        "quote",
        "projektanfrage",
    ),
}

_DEFAULT_ROUTE: dict[str, dict[str, str]] = {
    "lead": {"owner_role": "OPERATOR", "queue": "leads_inbox", "priority": "normal"},
    "support": {
        "owner_role": "OPERATOR",
        "queue": "support_inbox",
        "priority": "high",
    },
    "invoice": {"owner_role": "OFFICE", "queue": "finance_inbox", "priority": "normal"},
    "appointment": {
        "owner_role": "OFFICE",
        "queue": "scheduling_inbox",
        "priority": "high",
    },
    "unknown": {"owner_role": "OPERATOR", "queue": "triage_inbox", "priority": "low"},
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _compact_summary(value: str, *, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _score_label(text: str, metadata_text: str, label: str) -> tuple[float, list[str]]:
    tokens = _KEYWORDS.get(label, ())
    score = 0.0
    hits: list[str] = []
    for token in tokens:
        token_norm = _normalize_text(token)
        in_body = token_norm in text
        in_meta = token_norm in metadata_text
        if in_body:
            score += 0.28
            hits.append(token)
        if in_meta:
            score += 0.18
            if token not in hits:
                hits.append(token)
    return score, hits


def triage_message(text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    body_text = _normalize_text(text)
    metadata = metadata if isinstance(metadata, dict) else {}
    metadata_text = _normalize_text(" ".join(str(v or "") for v in metadata.values()))
    if not body_text:
        raise ValueError("empty_text")

    scored: list[tuple[str, float, list[str]]] = []
    for label in ("lead", "support", "invoice", "appointment"):
        score, hits = _score_label(body_text, metadata_text, label)
        scored.append((label, score, hits))

    scored.sort(key=lambda item: item[1], reverse=True)
    best_label, best_score, best_hits = scored[0]
    if best_score < 0.30:
        best_label = "unknown"
        best_score = 0.25
        best_hits = []

    confidence = max(0.0, min(0.99, round(best_score, 2)))
    route = dict(_DEFAULT_ROUTE[best_label])
    if route.get("priority") not in PRIORITIES:
        route["priority"] = "normal"

    return {
        "label": best_label,
        "confidence": confidence,
        "summary": _compact_summary(text),
        "route": route,
        "signals": best_hits[:6],
    }
