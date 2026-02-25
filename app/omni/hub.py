from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from email.utils import getaddresses
from hashlib import sha256
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.core import logic as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.knowledge import knowledge_redact_text

from .channels import ingest_email_sim

ALLOWED_CHANNELS = {"email", "chat", "phone"}
ALLOWED_DIRECTIONS = {"inbound", "outbound"}

MAX_CHANNEL_REF = 512
MAX_TEXT_FIELD = 20_000
MAX_FROM_TO = 1_000
MAX_FIXTURE_SIZE = 10 * 1024 * 1024
MAX_LIST_LIMIT = 50

DOMAIN_RE = re.compile(r"^[a-z0-9.-]{1,253}$")
ANGLE_RE = re.compile(r"^<(.+)>$")
WS_RE = re.compile(r"\s+")


def _tenant(tenant_id: str) -> str:
    tenant = legacy_core._effective_tenant(tenant_id)  # type: ignore[attr-defined]
    if not tenant:
        tenant = legacy_core._effective_tenant(legacy_core.TENANT_DEFAULT)  # type: ignore[attr-defined]
    return tenant or "default"


def _db() -> sqlite3.Connection:
    return legacy_core._db()  # type: ignore[attr-defined]


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def normalize_message_id(msgid: str | None) -> str | None:
    raw = str(msgid or "").replace("\x00", "").strip()
    if not raw:
        return None
    m = ANGLE_RE.match(raw)
    if m:
        raw = m.group(1)
    raw = raw.strip("<>").strip().lower()
    raw = WS_RE.sub("", raw)
    if not raw:
        return None
    if len(raw) > MAX_CHANNEL_REF:
        raw = raw[:MAX_CHANNEL_REF]
    return raw


def _clean_text(value: str | None, *, max_len: int) -> str:
    text = str(value or "").replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    text = WS_RE.sub(" ", text).strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _domain_only(addr: str | None) -> str | None:
    value = str(addr or "").strip().lower()
    if "@" not in value:
        return None
    domain = value.split("@", 1)[1].strip(" .")
    if not domain or not DOMAIN_RE.match(domain):
        return None
    return domain


def _address_token(addr: str | None) -> str | None:
    value = str(addr or "").strip().lower()
    if not value or "@" not in value:
        return None
    return sha256_hex(value)


def _tokenize_addresses(value: str | None) -> tuple[list[str], list[str]]:
    domains: list[str] = []
    tokens: list[str] = []
    addresses = getaddresses([str(value or "")])
    for _name, addr in addresses:
        domain = _domain_only(addr)
        if domain:
            domains.append(domain)
        token = _address_token(addr)
        if token:
            tokens.append(token)
    return sorted(set(domains)), sorted(set(tokens))


def _parse_payload_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_preview(payload: dict[str, Any]) -> tuple[str, str]:
    subject = _clean_text(str(payload.get("subject_redacted") or ""), max_len=180)
    body = _clean_text(str(payload.get("body_redacted") or ""), max_len=400)
    if len(body) > 160:
        body = body[:160]
    return subject, body


def redact_payload(
    raw_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = raw_payload if isinstance(raw_payload, dict) else {}

    from_raw = _clean_text(str(raw.get("from") or ""), max_len=MAX_FROM_TO)
    to_raw = _clean_text(str(raw.get("to") or ""), max_len=MAX_FROM_TO)
    subject_raw = _clean_text(str(raw.get("subject") or ""), max_len=500)
    body_raw = str(raw.get("body") or "").replace("\x00", " ")
    if len(body_raw) > MAX_TEXT_FIELD:
        body_raw = body_raw[:MAX_TEXT_FIELD]

    from_domains, from_tokens = _tokenize_addresses(from_raw)
    to_domains, to_tokens = _tokenize_addresses(to_raw)
    subject_redacted = knowledge_redact_text(subject_raw, max_len=500)
    body_redacted = knowledge_redact_text(body_raw, max_len=MAX_TEXT_FIELD)

    redacted = {
        "schema_version": 1,
        "from_domain": from_domains[0] if from_domains else None,
        "to_domains": to_domains,
        "from_token": from_tokens[0] if from_tokens else None,
        "to_tokens": to_tokens,
        "subject_redacted": subject_redacted,
        "body_redacted": body_redacted,
        "body_truncated": bool(raw.get("body_truncated")),
        "used_html_fallback": bool(raw.get("used_html_fallback")),
    }
    findings = {
        "schema_version": 1,
        "from_tokenized": bool(redacted["from_token"]),
        "to_token_count": len(to_tokens),
        "subject_changed": bool(subject_raw != subject_redacted),
        "body_changed": bool(body_raw != body_redacted),
        "body_was_truncated_pre_redaction": bool(raw.get("body_truncated")),
    }
    return redacted, findings


def _row_to_public(row: dict[str, Any]) -> dict[str, Any]:
    payload = _parse_payload_json(str(row.get("redacted_payload_json") or ""))
    findings = _parse_payload_json(str(row.get("redaction_findings_json") or ""))
    preview_subject, preview_body = _safe_preview(payload)
    return {
        "id": str(row.get("id") or ""),
        "tenant_id": str(row.get("tenant_id") or ""),
        "channel": str(row.get("channel") or ""),
        "channel_ref": row.get("channel_ref"),
        "channel_ref_norm": row.get("channel_ref_norm"),
        "direction": str(row.get("direction") or ""),
        "occurred_at": str(row.get("occurred_at") or ""),
        "created_at": str(row.get("created_at") or ""),
        "audit_hash": str(row.get("audit_hash") or ""),
        "payload": payload,
        "findings": findings,
        "preview_subject": preview_subject,
        "preview_body": preview_body,
    }


def _validate_event_draft(
    draft: dict[str, Any],
) -> tuple[str, str | None, str, str, dict[str, Any]]:
    channel = _clean_text(str(draft.get("channel") or ""), max_len=32).lower()
    if channel not in ALLOWED_CHANNELS:
        raise ValueError("validation_error")
    channel_ref_raw = draft.get("channel_ref")
    channel_ref = _clean_text(
        str(channel_ref_raw) if channel_ref_raw is not None else "",
        max_len=MAX_CHANNEL_REF,
    )
    direction = _clean_text(
        str(draft.get("direction") or "inbound"), max_len=16
    ).lower()
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError("validation_error")
    occurred_at = _clean_text(str(draft.get("occurred_at") or _now_iso()), max_len=40)
    raw_payload = draft.get("raw_payload")
    if not isinstance(raw_payload, dict):
        raise ValueError("validation_error")
    return channel, channel_ref or None, direction, occurred_at, raw_payload


def store_event(
    tenant_id: str,
    event_draft: dict[str, Any],
    *,
    actor_user_id: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    channel, channel_ref, direction, occurred_at, raw_payload = _validate_event_draft(
        event_draft
    )
    channel_ref_norm = normalize_message_id(channel_ref)
    redacted_payload, findings = redact_payload(raw_payload)
    redacted_payload_json = canonical_json(redacted_payload)
    findings_json = canonical_json(findings)
    audit_hash = sha256_hex(f"{redacted_payload_json}|{tenant}")
    row_id = _new_id()
    created_at = _now_iso()

    if dry_run:
        return {
            "ok": True,
            "reason": None,
            "committed": False,
            "duplicate": False,
            "event_id": row_id,
            "record": {
                "id": row_id,
                "tenant_id": tenant,
                "channel": channel,
                "channel_ref": channel_ref,
                "channel_ref_norm": channel_ref_norm,
                "direction": direction,
                "occurred_at": occurred_at,
                "created_at": created_at,
                "audit_hash": audit_hash,
                "payload": redacted_payload,
                "findings": findings,
                "preview_subject": _safe_preview(redacted_payload)[0],
                "preview_body": _safe_preview(redacted_payload)[1],
            },
        }

    if _is_read_only():
        raise PermissionError("read_only")

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        con.execute(
            """
            INSERT OR IGNORE INTO conversation_events(
              id, tenant_id, channel, channel_ref, channel_ref_norm, direction,
              occurred_at, redacted_payload_json, redaction_findings_json, audit_hash, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row_id,
                tenant,
                channel,
                channel_ref,
                channel_ref_norm,
                direction,
                occurred_at,
                redacted_payload_json,
                findings_json,
                audit_hash,
                created_at,
            ),
        )

        duplicate = con.total_changes == 0
        if duplicate:
            if channel_ref_norm:
                row = con.execute(
                    """
                    SELECT id, tenant_id, channel, channel_ref, channel_ref_norm, direction,
                           occurred_at, redacted_payload_json, redaction_findings_json, audit_hash, created_at
                    FROM conversation_events
                    WHERE tenant_id=? AND channel=? AND channel_ref_norm=?
                    LIMIT 1
                    """,
                    (tenant, channel, channel_ref_norm),
                ).fetchone()
            else:
                row = con.execute(
                    """
                    SELECT id, tenant_id, channel, channel_ref, channel_ref_norm, direction,
                           occurred_at, redacted_payload_json, redaction_findings_json, audit_hash, created_at
                    FROM conversation_events
                    WHERE tenant_id=? AND channel=? AND audit_hash=?
                    LIMIT 1
                    """,
                    (tenant, channel, audit_hash),
                ).fetchone()
        else:
            row = con.execute(
                """
                SELECT id, tenant_id, channel, channel_ref, channel_ref_norm, direction,
                       occurred_at, redacted_payload_json, redaction_findings_json, audit_hash, created_at
                FROM conversation_events
                WHERE tenant_id=? AND id=?
                LIMIT 1
                """,
                (tenant, row_id),
            ).fetchone()

        if row is None:
            raise ValueError("db_error")

        row_public = _row_to_public(dict(row))
        if not duplicate:
            event_append(
                event_type="conversation_event_ingested",
                entity_type="conversation_event",
                entity_id=entity_id_int(str(row_public["id"])),
                payload={
                    "schema_version": 1,
                    "source": "omni/hub",
                    "actor_user_id": actor_user_id,
                    "tenant_id": tenant,
                    "data": {
                        "event_id": row_public["id"],
                        "channel": channel,
                        "direction": direction,
                        "has_channel_ref": bool(channel_ref_norm),
                    },
                },
                con=con,
            )
        return {
            "ok": True,
            "reason": None,
            "committed": True,
            "duplicate": duplicate,
            "event_id": str(row_public["id"]),
            "record": row_public,
        }

    return _run_write_txn(_tx)


def ingest_fixture(
    tenant_id: str,
    *,
    channel: str,
    fixture_path: Path | str,
    actor_user_id: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    tenant = _tenant(tenant_id)
    path = Path(str(fixture_path))
    if not path.exists() or not path.is_file():
        raise ValueError("fixture_not_found")
    if path.stat().st_size > MAX_FIXTURE_SIZE:
        raise ValueError("payload_too_large")

    channel_norm = _clean_text(channel, max_len=32).lower()
    if channel_norm == "email":
        drafts = ingest_email_sim(tenant, path)
    else:
        raise ValueError("unsupported_channel")

    results: list[dict[str, Any]] = []
    for draft in drafts:
        results.append(
            store_event(
                tenant,
                draft,
                actor_user_id=actor_user_id,
                dry_run=dry_run,
            )
        )
    return {
        "ok": True,
        "tenant_id": tenant,
        "channel": channel_norm,
        "fixture": path.name,
        "dry_run": bool(dry_run),
        "committed": not bool(dry_run),
        "results": results,
    }


def list_events(
    tenant_id: str,
    *,
    channel: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    tenant = _tenant(tenant_id)
    size = max(1, min(int(limit or 50), MAX_LIST_LIMIT))
    clauses = ["tenant_id=?"]
    params: list[Any] = [tenant]
    ch = _clean_text(channel or "", max_len=32).lower() if channel else ""
    if ch:
        if ch not in ALLOWED_CHANNELS:
            raise ValueError("validation_error")
        clauses.append("channel=?")
        params.append(ch)
    where_sql = " AND ".join(clauses)

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            rows = con.execute(
                f"""
                SELECT id, tenant_id, channel, channel_ref, channel_ref_norm, direction,
                       occurred_at, redacted_payload_json, redaction_findings_json, audit_hash, created_at
                FROM conversation_events
                WHERE {where_sql}
                ORDER BY occurred_at DESC, created_at DESC
                LIMIT ?
                """,
                tuple(params + [size]),
            ).fetchall()
            return [_row_to_public(dict(r)) for r in rows]
        finally:
            con.close()


def get_event(tenant_id: str, event_id: str) -> dict[str, Any] | None:
    tenant = _tenant(tenant_id)
    event_id_n = _clean_text(event_id, max_len=64)
    if not event_id_n:
        raise ValueError("validation_error")
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            row = con.execute(
                """
                SELECT id, tenant_id, channel, channel_ref, channel_ref_norm, direction,
                       occurred_at, redacted_payload_json, redaction_findings_json, audit_hash, created_at
                FROM conversation_events
                WHERE tenant_id=? AND id=?
                LIMIT 1
                """,
                (tenant, event_id_n),
            ).fetchone()
            return _row_to_public(dict(row)) if row else None
        finally:
            con.close()
