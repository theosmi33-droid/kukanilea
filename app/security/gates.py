from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Iterable, Mapping
from urllib.parse import unquote

DEFAULT_CONFIRM_TOKENS = frozenset({"CONFIRM", "YES", "TRUE", "1"})

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(?:^|\b)(?:drop|truncate|alter)\s+table\b"),
    re.compile(r"(?i)(?:\bunion\b\s+(?:all\s+)?select\b)"),
    re.compile(r"(?i)(?:'\s*or\s*'1'\s*=\s*'1|\bor\b\s+1\s*=\s*1)"),
    re.compile(r"(?i)(?:--|/\*|\*/|;\s*(?:drop|delete|insert|update|select)\b)"),
    re.compile(r"(?i)<\s*script\b"),
    re.compile(r"(?i)\bjavascript:\s*"),
    re.compile(r"(?i)\bsystem\s+override\b"),
    re.compile(r"(?i)\bignore\s+instructions?\b"),
    re.compile(r"(?i)\bprompt\s+jailbreak\b"),
    re.compile(r"(?i)\bdeveloper\s+mode\b"),
    re.compile(r"(?i)\bdo\s+anything\s+now\b|\bdan\s+mode\b"),
    re.compile(r"(?i)\b(?:bypass|disable)\s+(?:all\s+)?(?:security|guardrails?|safety)\b"),
    re.compile(r"(?i)\b(?:reveal|print)\s+(?:the\s+)?(?:system\s+prompt|hidden\s+instructions?)\b"),
    re.compile(r"(?i)\b(?:xp_cmdshell|exec\s*\()"),
    re.compile(r"(?i)\b(?:sleep\s*\(|benchmark\s*\()"),
    re.compile(r"(?i)\b(?:information_schema|pg_catalog|sqlite_master)\b"),
    re.compile(r"(?i)\.\./|\.\.\\"),
)


@dataclass(frozen=True)
class InjectionFinding:
    field: str
    value: str
    pattern: str


@dataclass(frozen=True)
class ConfirmGatePolicy:
    route: str
    fields: tuple[str, ...]
    required: bool = True


CRITICAL_CONFIRM_GATE_MATRIX: tuple[ConfirmGatePolicy, ...] = (
    ConfirmGatePolicy(route="/admin/settings/profile", fields=("language", "timezone", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/users/create", fields=("username", "password", "tenant_id", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/users/update", fields=("username", "tenant_id", "role", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/users/disable", fields=("username", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/users/delete", fields=("username", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/tenants/add", fields=("name", "db_path", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/license/upload", fields=("confirm", "license_json")),
    ConfirmGatePolicy(route="/admin/settings/system", fields=("language", "timezone", "backup_interval", "log_level", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/branding", fields=("app_name", "primary_color", "footer_text", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/backup/run", fields=("confirm",)),
    ConfirmGatePolicy(route="/admin/settings/backup/restore", fields=("backup_name", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/mesh/connect", fields=("peer_ip", "peer_port", "confirm")),
    ConfirmGatePolicy(route="/admin/settings/mesh/rotate-key", fields=("confirm",)),
    ConfirmGatePolicy(route="/admin/context/switch", fields=("tenant_id",), required=False),
    # PKG-GRD-02: API Hardening
    ConfirmGatePolicy(route="/api/kalender/events", fields=("title", "starts_at", "confirm")),
    ConfirmGatePolicy(route="/api/kalender/invitations", fields=("title", "starts_at", "confirm")),
    ConfirmGatePolicy(route="/api/aufgaben", fields=("title", "confirm")),
    ConfirmGatePolicy(route="/api/projekte", fields=("name", "confirm")),
    ConfirmGatePolicy(route="/api/intake/execute", fields=("confirm",)),
)

CRITICAL_CONFIRM_GATE_BY_ROUTE = {row.route: row for row in CRITICAL_CONFIRM_GATE_MATRIX}


def confirm_gate(value: str | None, accepted_tokens: Iterable[str] = DEFAULT_CONFIRM_TOKENS) -> bool:
    token = str(value or "").strip().upper()
    normalized = {str(item).strip().upper() for item in accepted_tokens if str(item).strip()}
    return bool(token and token in normalized)


def detect_injection(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidates = (text, unquote(text), unescape(text), unescape(unquote(text)))
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        for pattern in INJECTION_PATTERNS:
            if pattern.search(normalized):
                return pattern.pattern
    return None


def scan_payload_for_injection(payload: Mapping[str, str | None], fields: Iterable[str]) -> InjectionFinding | None:
    for field in fields:
        raw = payload.get(field)
        matched = detect_injection(raw)
        if matched:
            return InjectionFinding(field=field, value=str(raw or ""), pattern=matched)
    return None


def parse_json_object(raw_payload: str | bytes | None) -> dict[str, Any] | None:
    if raw_payload is None:
        return None
    text = raw_payload.decode("utf-8", errors="ignore") if isinstance(raw_payload, bytes) else str(raw_payload)
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def scan_nested_payload_for_injection(payload: Any, field: str = "payload") -> InjectionFinding | None:
    if payload is None:
        return None
    if isinstance(payload, str):
        matched = detect_injection(payload)
        if matched:
            return InjectionFinding(field=field, value=payload, pattern=matched)
        return None
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            hit = scan_nested_payload_for_injection(value, f"{field}.{key}")
            if hit:
                return hit
        return None
    if isinstance(payload, (list, tuple, set)):
        for index, value in enumerate(payload):
            hit = scan_nested_payload_for_injection(value, f"{field}[{index}]")
            if hit:
                return hit
    return None
