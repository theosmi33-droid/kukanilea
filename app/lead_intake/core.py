from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app, has_app_context

import kukanilea_core_v3_fixed as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

LEAD_STATUSES = {"new", "contacted", "qualified", "lost", "won", "screening", "ignored"}
LEAD_SOURCES = {"call", "email", "webform", "manual"}
CALL_DIRECTIONS = {"inbound", "outbound"}
APPOINTMENT_STATUSES = {"pending", "accepted", "declined", "rescheduled"}
BLOCKLIST_KINDS = {"email", "domain", "phone"}
LEAD_PRIORITIES = {"normal", "high"}
ENTITY_LINK_TYPES = {"related", "converted_from", "references", "attachment"}

MAX_CONTACT_NAME = 200
MAX_CONTACT_EMAIL = 320
MAX_CONTACT_PHONE = 32
MAX_SUBJECT = 500
MAX_DEAL_TITLE = 200
MAX_MESSAGE = 20000
MAX_NOTES = 20000
MAX_BLOCKED_REASON = 200
MAX_BLOCKLIST_REASON = 2000
MAX_ASSIGNED_TO = 128
MAX_BLOCK_VALUE = 320
MAX_CLAIM_TTL_SECONDS = 28800
MIN_CLAIM_TTL_SECONDS = 60
DEFAULT_CLAIM_TTL_SECONDS = 900


class ConflictError(ValueError):
    def __init__(self, code: str, *, details: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.details = details or {}


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


def _ensure_writable() -> None:
    if _is_read_only():
        raise ValueError("read_only")


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _read_rows(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            rows = con.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def _validate_len(
    value: str | None, max_len: int, code: str = "validation_error"
) -> str:
    v = (value or "").strip()
    if len(v) > max_len:
        raise ValueError(code)
    return v


def normalize_email(value: str | None) -> str | None:
    v = (value or "").strip().lower()
    if not v:
        return None
    if len(v) > MAX_CONTACT_EMAIL or "@" not in v or " " in v:
        raise ValueError("validation_error")
    local, domain = v.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise ValueError("validation_error")
    return v


def extract_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].strip().lower() or None


def normalize_phone(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    plus = raw.startswith("+")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError("validation_error")
    normalized = f"+{digits}" if plus else digits
    if len(normalized) > MAX_CONTACT_PHONE:
        raise ValueError("validation_error")
    return normalized


def _parse_response_due(value: str | None) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v)
    except Exception:
        raise ValueError("validation_error")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat(timespec="seconds")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _clamp_claim_ttl(ttl_seconds: int | None) -> int:
    ttl = int(ttl_seconds or DEFAULT_CLAIM_TTL_SECONDS)
    return max(MIN_CLAIM_TTL_SECONDS, min(ttl, MAX_CLAIM_TTL_SECONDS))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _canonical_pair(
    left_type: str, left_id: str, right_type: str, right_id: str
) -> tuple[str, str, str, str]:
    left = (left_type, left_id)
    right = (right_type, right_id)
    if left <= right:
        return left_type, left_id, right_type, right_id
    return right_type, right_id, left_type, left_id


def _next_quote_number(con: sqlite3.Connection, tenant_id: str) -> str:
    helper = getattr(legacy_core, "_next_quote_number", None)
    if callable(helper):
        return str(helper(con, tenant_id))
    row = con.execute(
        "SELECT COUNT(*) AS cnt FROM quotes WHERE tenant_id=?",
        (tenant_id,),
    ).fetchone()
    next_idx = int((row["cnt"] if row else 0) or 0) + 1
    return f"Q-{next_idx:06d}"


def _insert_entity_link(
    con: sqlite3.Connection,
    *,
    tenant_id: str,
    left_type: str,
    left_id: str,
    right_type: str,
    right_id: str,
    link_type: str,
    actor_user_id: str | None,
    source: str,
) -> str:
    link_kind = legacy_core.normalize_component(link_type).lower()
    if link_kind not in ENTITY_LINK_TYPES:
        raise ValueError("validation_error")
    a_type, a_id, b_type, b_id = _canonical_pair(
        left_type, left_id, right_type, right_id
    )
    link_id = _new_id()
    now = _now_iso()
    try:
        con.execute(
            """
            INSERT INTO entity_links(
              id, tenant_id, a_type, a_id, b_type, b_id, link_type, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (link_id, tenant_id, a_type, a_id, b_type, b_id, link_kind, now, now),
        )
    except sqlite3.IntegrityError as exc:
        if "unique" not in str(exc).lower():
            raise
        row = con.execute(
            """
            SELECT id
            FROM entity_links
            WHERE tenant_id=? AND a_type=? AND a_id=? AND b_type=? AND b_id=? AND link_type=?
            LIMIT 1
            """,
            (tenant_id, a_type, a_id, b_type, b_id, link_kind),
        ).fetchone()
        return str(row["id"] if row else "")

    event_append(
        event_type="entity_link_created",
        entity_type="entity_link",
        entity_id=entity_id_int(link_id),
        payload={
            "schema_version": 1,
            "source": source,
            "actor_user_id": actor_user_id,
            "tenant_id": tenant_id,
            "data": {
                "link_id": link_id,
                "a_type": a_type,
                "a_id": a_id,
                "b_type": b_type,
                "b_id": b_id,
                "link_type": link_kind,
            },
        },
        con=con,
    )
    return link_id


def _lead_exists(con: sqlite3.Connection, tenant_id: str, lead_id: str) -> bool:
    row = con.execute(
        "SELECT id FROM leads WHERE tenant_id=? AND id=? LIMIT 1",
        (tenant_id, lead_id),
    ).fetchone()
    return bool(row)


def _claim_row(con: sqlite3.Connection, tenant_id: str, lead_id: str):
    return con.execute(
        "SELECT id, tenant_id, lead_id, claimed_by, claimed_at, claimed_until, released_at, release_reason, created_at, updated_at "
        "FROM lead_claims WHERE tenant_id=? AND lead_id=? LIMIT 1",
        (tenant_id, lead_id),
    ).fetchone()


def _claim_is_active(row: dict[str, Any], now_dt: datetime) -> bool:
    if row.get("released_at"):
        return False
    until_dt = _parse_iso(str(row.get("claimed_until") or ""))
    return bool(until_dt and until_dt > now_dt)


def _claim_is_expired(row: dict[str, Any], now_dt: datetime) -> bool:
    if row.get("released_at"):
        return False
    until_dt = _parse_iso(str(row.get("claimed_until") or ""))
    return bool(until_dt and until_dt <= now_dt)


def _claim_details(row: dict[str, Any], now_dt: datetime) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "tenant_id": str(row.get("tenant_id") or ""),
        "lead_id": str(row.get("lead_id") or ""),
        "claimed_by": str(row.get("claimed_by") or ""),
        "claimed_at": str(row.get("claimed_at") or ""),
        "claimed_until": str(row.get("claimed_until") or ""),
        "released_at": str(row.get("released_at") or "") or None,
        "release_reason": str(row.get("release_reason") or "") or None,
        "active": _claim_is_active(row, now_dt),
        "expired": _claim_is_expired(row, now_dt),
    }


def _expire_claim_row(
    con: sqlite3.Connection,
    tenant_id: str,
    row: dict[str, Any],
    *,
    now_iso: str,
    actor_user_id: str | None = None,
) -> None:
    if row.get("released_at"):
        return
    claim_id = str(row.get("id") or "")
    lead_id = str(row.get("lead_id") or "")
    if not claim_id or not lead_id:
        return
    con.execute(
        "UPDATE lead_claims SET released_at=?, release_reason='expired', updated_at=? WHERE tenant_id=? AND id=? AND released_at IS NULL",
        (now_iso, now_iso, tenant_id, claim_id),
    )
    event_append(
        event_type="lead_claim_expired",
        entity_type="lead",
        entity_id=entity_id_int(lead_id),
        payload={
            "schema_version": 1,
            "source": "lead_intake/lead_claims_auto_expire",
            "actor_user_id": actor_user_id,
            "tenant_id": tenant_id,
            "data": {
                "lead_id": lead_id,
                "claimed_by": str(row.get("claimed_by") or ""),
                "claimed_until": str(row.get("claimed_until") or ""),
            },
        },
        con=con,
    )


def _lead_require_claim_or_free_tx(
    con: sqlite3.Connection,
    tenant_id: str,
    lead_id: str,
    actor_user_id: str | None,
) -> None:
    now_iso = _now_iso()
    now_dt = _parse_iso(now_iso) or datetime.now(UTC)
    row_any = _claim_row(con, tenant_id, lead_id)
    if not row_any:
        return
    row = dict(row_any)
    if _claim_is_expired(row, now_dt):
        _expire_claim_row(
            con,
            tenant_id,
            row,
            now_iso=now_iso,
            actor_user_id=actor_user_id,
        )
        return
    if _claim_is_active(row, now_dt) and str(row.get("claimed_by") or "") != str(
        actor_user_id or ""
    ):
        raise ConflictError(
            "lead_claimed",
            details={
                "lead_id": lead_id,
                "claimed_by": str(row.get("claimed_by") or ""),
                "claimed_until": str(row.get("claimed_until") or ""),
            },
        )


def _find_customer_for_contact(
    con: sqlite3.Connection,
    tenant_id: str,
    email: str | None,
    phone: str | None,
) -> str | None:
    if email:
        row = con.execute(
            """
            SELECT customer_id
            FROM contacts
            WHERE tenant_id=? AND LOWER(COALESCE(email,''))=LOWER(?)
              AND customer_id IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (tenant_id, email),
        ).fetchone()
        if row and row["customer_id"]:
            return str(row["customer_id"])
    if phone:
        row = con.execute(
            """
            SELECT customer_id
            FROM contacts
            WHERE tenant_id=?
              AND REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone,''), ' ', ''), '-', ''), '(', ''), ')', '') LIKE ?
              AND customer_id IS NOT NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (tenant_id, f"%{phone.replace('+', '')}"),
        ).fetchone()
        if row and row["customer_id"]:
            return str(row["customer_id"])
    return None


def _blocklist_match(
    con: sqlite3.Connection,
    tenant_id: str,
    email: str | None,
    phone: str | None,
) -> str | None:
    candidates: list[tuple[str, str]] = []
    if email:
        candidates.append(("email", email))
        domain = extract_domain(email)
        if domain:
            candidates.append(("domain", domain))
    if phone:
        candidates.append(("phone", phone))
    for kind, value in candidates:
        row = con.execute(
            "SELECT 1 FROM lead_blocklist WHERE tenant_id=? AND kind=? AND value=? LIMIT 1",
            (tenant_id, kind, value),
        ).fetchone()
        if row:
            return kind
    return None


def leads_create(
    tenant_id: str,
    source: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    subject: str,
    message: str,
    customer_id: str | None = None,
    notes: str | None = None,
    actor_user_id: str | None = None,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    src = legacy_core.normalize_component(source).lower()
    if src not in LEAD_SOURCES:
        raise ValueError("validation_error")

    name_norm = _validate_len(contact_name, MAX_CONTACT_NAME)
    email_norm = normalize_email(contact_email)
    phone_norm = normalize_phone(contact_phone)
    subject_norm = _validate_len(subject, MAX_SUBJECT)
    message_norm = _validate_len(message, MAX_MESSAGE)
    notes_norm = _validate_len(notes, MAX_NOTES)

    lead_id = _new_id()
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> str:
        customer_ref = customer_id
        if customer_ref:
            row = con.execute(
                "SELECT id FROM customers WHERE tenant_id=? AND id=?",
                (t, customer_ref),
            ).fetchone()
            if not row:
                raise ValueError("not_found")

        matched_kind = _blocklist_match(con, t, email_norm, phone_norm)
        blocked_reason = None
        if matched_kind:
            status = "ignored"
            blocked_reason = f"blocklist:{matched_kind}"
        else:
            if not customer_ref:
                customer_ref = _find_customer_for_contact(
                    con, t, email_norm, phone_norm
                )
            status = "new" if customer_ref else "screening"

        con.execute(
            """
            INSERT INTO leads(
              id, tenant_id, status, source, customer_id,
              contact_name, contact_email, contact_phone,
              subject, message, notes, priority, pinned,
              assigned_to, response_due, screened_at, blocked_reason,
              created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                lead_id,
                t,
                status,
                src,
                customer_ref,
                name_norm,
                email_norm,
                phone_norm,
                subject_norm,
                message_norm,
                notes_norm,
                "normal",
                0,
                None,
                None,
                now if status != "screening" else None,
                blocked_reason,
                now,
                now,
            ),
        )

        if matched_kind:
            event_type = "lead_blocked"
            data = {
                "lead_id": lead_id,
                "status": status,
                "source": src,
                "customer_id": customer_ref,
                "kind": matched_kind,
                "reason": blocked_reason,
            }
        else:
            event_type = "lead_created"
            data = {
                "lead_id": lead_id,
                "status": status,
                "source": src,
                "customer_id": customer_ref,
            }

        event_append(
            event_type=event_type,
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_create",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": data,
            },
            con=con,
        )
        return lead_id

    return _run_write_txn(_tx)


def leads_get(tenant_id: str, lead_id: str) -> dict[str, Any] | None:
    t = _tenant(tenant_id)
    rows = _read_rows(
        """
        SELECT id, tenant_id, status, source, customer_id, contact_name, contact_email,
               contact_phone, subject, message, notes, priority, pinned,
               assigned_to, response_due, screened_at, blocked_reason,
               created_at, updated_at
        FROM leads
        WHERE tenant_id=? AND id=?
        LIMIT 1
        """,
        (t, lead_id),
    )
    return rows[0] if rows else None


def lead_claim_get(tenant_id: str, lead_id: str) -> dict[str, Any] | None:
    t = _tenant(tenant_id)
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            row = _claim_row(con, t, lead_id)
            if not row:
                return None
            now_dt = _parse_iso(_now_iso()) or datetime.now(UTC)
            return _claim_details(dict(row), now_dt)
        finally:
            con.close()


def lead_claims_for_leads(
    tenant_id: str, lead_ids: list[str]
) -> dict[str, dict[str, Any] | None]:
    t = _tenant(tenant_id)
    ids = [str(x or "").strip() for x in lead_ids if str(x or "").strip()]
    if not ids:
        return {}
    uniq_ids: list[str] = list(dict.fromkeys(ids))
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            now_dt = _parse_iso(_now_iso()) or datetime.now(UTC)
            out: dict[str, dict[str, Any] | None] = {}
            for lead_id in uniq_ids:
                row = _claim_row(con, t, lead_id)
                out[lead_id] = _claim_details(dict(row), now_dt) if row else None
            return out
        finally:
            con.close()


def lead_claim(
    tenant_id: str,
    lead_id: str,
    actor_user_id: str,
    ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
    force: bool = False,
) -> dict[str, Any]:
    _ensure_writable()
    t = _tenant(tenant_id)
    actor = _validate_len(actor_user_id, MAX_ASSIGNED_TO)
    if not actor:
        raise ValueError("validation_error")
    ttl = _clamp_claim_ttl(ttl_seconds)

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        if not _lead_exists(con, t, lead_id):
            raise ValueError("not_found")
        now_iso = _now_iso()
        now_dt = _parse_iso(now_iso) or datetime.now(UTC)

        existing_any = _claim_row(con, t, lead_id)
        if existing_any:
            existing = dict(existing_any)
            if _claim_is_expired(existing, now_dt):
                _expire_claim_row(
                    con,
                    t,
                    existing,
                    now_iso=now_iso,
                    actor_user_id=actor,
                )
                existing = dict(_claim_row(con, t, lead_id) or {})

            if (
                existing
                and _claim_is_active(existing, now_dt)
                and str(existing.get("claimed_by") or "") != actor
            ):
                if not force:
                    raise ConflictError(
                        "lead_claimed",
                        details={
                            "lead_id": lead_id,
                            "claimed_by": str(existing.get("claimed_by") or ""),
                            "claimed_until": str(existing.get("claimed_until") or ""),
                        },
                    )
                con.execute(
                    "UPDATE lead_claims SET released_at=?, release_reason='reclaimed', updated_at=? WHERE tenant_id=? AND lead_id=? AND released_at IS NULL",
                    (now_iso, now_iso, t, lead_id),
                )
                event_append(
                    event_type="lead_claim_reclaimed",
                    entity_type="lead",
                    entity_id=entity_id_int(lead_id),
                    payload={
                        "schema_version": 1,
                        "source": "lead_intake/lead_claim",
                        "actor_user_id": actor,
                        "tenant_id": t,
                        "data": {
                            "lead_id": lead_id,
                            "prev_claimed_by": str(existing.get("claimed_by") or ""),
                        },
                    },
                    con=con,
                )

        claim_until = (
            (now_dt + timedelta(seconds=ttl))
            .astimezone(UTC)
            .isoformat(timespec="seconds")
        )
        existing_final = _claim_row(con, t, lead_id)
        if existing_final:
            claim_id = str(existing_final["id"])
            con.execute(
                "UPDATE lead_claims SET claimed_by=?, claimed_at=?, claimed_until=?, released_at=NULL, release_reason=NULL, updated_at=? WHERE tenant_id=? AND lead_id=?",
                (actor, now_iso, claim_until, now_iso, t, lead_id),
            )
        else:
            claim_id = _new_id()
            con.execute(
                "INSERT INTO lead_claims(id, tenant_id, lead_id, claimed_by, claimed_at, claimed_until, released_at, release_reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    claim_id,
                    t,
                    lead_id,
                    actor,
                    now_iso,
                    claim_until,
                    None,
                    None,
                    now_iso,
                    now_iso,
                ),
            )

        event_append(
            event_type="lead_claimed",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/lead_claim",
                "actor_user_id": actor,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "claimed_by": actor,
                    "claimed_until": claim_until,
                    "ttl_seconds": ttl,
                    "force": bool(force),
                },
            },
            con=con,
        )

        row = _claim_row(con, t, lead_id)
        payload = (
            _claim_details(dict(row), _parse_iso(now_iso) or now_dt)
            if row
            else {
                "id": claim_id,
                "tenant_id": t,
                "lead_id": lead_id,
                "claimed_by": actor,
                "claimed_at": now_iso,
                "claimed_until": claim_until,
                "released_at": None,
                "release_reason": None,
                "active": True,
                "expired": False,
            }
        )
        return payload

    return _run_write_txn(_tx)


def lead_release_claim(
    tenant_id: str,
    lead_id: str,
    actor_user_id: str,
    reason: str = "manual",
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    actor = _validate_len(actor_user_id, MAX_ASSIGNED_TO)
    reason_norm = _validate_len(reason, 40) or "manual"

    def _tx(con: sqlite3.Connection) -> None:
        row_any = _claim_row(con, t, lead_id)
        if not row_any:
            raise ValueError("not_found")
        row = dict(row_any)
        if row.get("released_at"):
            raise ConflictError("not_owner")
        if str(row.get("claimed_by") or "") != actor:
            raise ConflictError(
                "not_owner",
                details={
                    "lead_id": lead_id,
                    "claimed_by": str(row.get("claimed_by") or ""),
                },
            )
        now_iso = _now_iso()
        con.execute(
            "UPDATE lead_claims SET released_at=?, release_reason=?, updated_at=? WHERE tenant_id=? AND lead_id=? AND released_at IS NULL",
            (now_iso, reason_norm, now_iso, t, lead_id),
        )
        event_append(
            event_type="lead_claim_released",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/lead_release_claim",
                "actor_user_id": actor,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "claimed_by": actor,
                    "reason": reason_norm,
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def lead_claims_auto_expire(
    tenant_id: str,
    max_actions: int = 200,
    actor_user_id: str | None = None,
) -> int:
    _ensure_writable()
    t = _tenant(tenant_id)
    lim = max(1, min(int(max_actions), 1000))

    def _tx(con: sqlite3.Connection) -> int:
        now_iso = _now_iso()
        rows = con.execute(
            "SELECT id, tenant_id, lead_id, claimed_by, claimed_at, claimed_until, released_at, release_reason, created_at, updated_at FROM lead_claims WHERE tenant_id=? AND released_at IS NULL AND datetime(claimed_until) < datetime(?) ORDER BY claimed_until ASC LIMIT ?",
            (t, now_iso, lim),
        ).fetchall()
        count = 0
        for row in rows:
            _expire_claim_row(
                con,
                t,
                dict(row),
                now_iso=now_iso,
                actor_user_id=actor_user_id,
            )
            count += 1
        return count

    return int(_run_write_txn(_tx) or 0)


def lead_require_claim_or_free(
    tenant_id: str,
    lead_id: str,
    actor_user_id: str | None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)

    def _tx(con: sqlite3.Connection) -> None:
        if not _lead_exists(con, t, lead_id):
            raise ValueError("not_found")
        _lead_require_claim_or_free_tx(con, t, lead_id, actor_user_id)

    _run_write_txn(_tx)


def leads_list(
    tenant_id: str,
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    *,
    priority_only: bool = False,
    pinned_only: bool = False,
    assigned_to: str | None = None,
    due_mode: str | None = None,
    blocked_only: bool = False,
) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    clauses = ["tenant_id=?"]
    params: list[Any] = [t]

    st = legacy_core.normalize_component(status).lower()
    if st:
        if st not in LEAD_STATUSES:
            raise ValueError("validation_error")
        clauses.append("status=?")
        params.append(st)

    src = legacy_core.normalize_component(source).lower()
    if src:
        if src not in LEAD_SOURCES:
            raise ValueError("validation_error")
        clauses.append("source=?")
        params.append(src)

    if priority_only:
        clauses.append("(priority='high' OR pinned=1)")

    if pinned_only:
        clauses.append("pinned=1")

    assigned_norm = _validate_len(assigned_to, MAX_ASSIGNED_TO) if assigned_to else ""
    if assigned_norm:
        clauses.append("assigned_to=?")
        params.append(assigned_norm)

    due = (due_mode or "").strip().lower()
    if due == "today":
        clauses.append("date(response_due)=date('now')")
    elif due == "overdue":
        clauses.append(
            "response_due IS NOT NULL AND datetime(response_due) < datetime('now')"
        )
    elif due:
        raise ValueError("validation_error")

    if blocked_only:
        clauses.append("(status='ignored' OR blocked_reason IS NOT NULL)")

    qq = legacy_core.normalize_component(q)
    if qq:
        clauses.append(
            "(LOWER(COALESCE(subject,'')) LIKE LOWER(?) OR LOWER(COALESCE(contact_name,'')) LIKE LOWER(?))"
        )
        params.extend([f"%{qq}%", f"%{qq}%"])

    where_sql = " AND ".join(clauses)
    return _read_rows(
        f"""
        SELECT id, tenant_id, status, source, customer_id, contact_name,
               contact_email, contact_phone, subject, message, notes,
               priority, pinned, assigned_to, response_due, screened_at,
               blocked_reason, created_at, updated_at
        FROM leads
        WHERE {where_sql}
        ORDER BY
          pinned DESC,
          CASE priority WHEN 'high' THEN 1 ELSE 0 END DESC,
          CASE WHEN response_due IS NULL THEN 1 ELSE 0 END ASC,
          response_due ASC,
          created_at DESC,
          id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [lim, off]),
    )


def leads_inbox_counts(
    tenant_id: str, assigned_to: str | None = None
) -> dict[str, int]:
    t = _tenant(tenant_id)
    assignee = _validate_len(assigned_to, MAX_ASSIGNED_TO) if assigned_to else ""
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            row = con.execute(
                """
                SELECT
                  COUNT(*) AS all_count,
                  SUM(CASE WHEN status='screening' THEN 1 ELSE 0 END) AS screening_count,
                  SUM(CASE WHEN priority='high' OR pinned=1 THEN 1 ELSE 0 END) AS priority_count,
                  SUM(CASE WHEN assigned_to=? THEN 1 ELSE 0 END) AS assigned_count,
                  SUM(CASE WHEN response_due IS NOT NULL AND date(response_due)=date('now') THEN 1 ELSE 0 END) AS due_today_count,
                  SUM(CASE WHEN response_due IS NOT NULL AND datetime(response_due) < datetime('now') THEN 1 ELSE 0 END) AS overdue_count,
                  SUM(CASE WHEN status='ignored' OR blocked_reason IS NOT NULL THEN 1 ELSE 0 END) AS blocked_count
                FROM leads
                WHERE tenant_id=?
                """,
                (assignee, t),
            ).fetchone()
            if not row:
                return {
                    "all": 0,
                    "screening": 0,
                    "priority": 0,
                    "assigned": 0,
                    "due_today": 0,
                    "overdue": 0,
                    "blocked": 0,
                }
            return {
                "all": int(row["all_count"] or 0),
                "screening": int(row["screening_count"] or 0),
                "priority": int(row["priority_count"] or 0),
                "assigned": int(row["assigned_count"] or 0),
                "due_today": int(row["due_today_count"] or 0),
                "overdue": int(row["overdue_count"] or 0),
                "blocked": int(row["blocked_count"] or 0),
            }
        finally:
            con.close()


def leads_update_status(
    tenant_id: str,
    lead_id: str,
    new_status: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    status_norm = legacy_core.normalize_component(new_status).lower()
    if status_norm not in LEAD_STATUSES:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT status, source, customer_id FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        prev = str(row["status"] or "")
        con.execute(
            "UPDATE leads SET status=?, updated_at=? WHERE tenant_id=? AND id=?",
            (status_norm, _now_iso(), t, lead_id),
        )
        event_append(
            event_type="lead_status_updated",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_update_status",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "prev_status": prev,
                    "status": status_norm,
                    "source": str(row["source"] or ""),
                    "customer_id": row["customer_id"],
                },
            },
            con=con,
        )
        return None

    _run_write_txn(_tx)


def leads_screen_accept(
    tenant_id: str, lead_id: str, actor_user_id: str | None = None
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT status FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        _lead_require_claim_or_free_tx(con, t, lead_id, actor_user_id)
        now = _now_iso()
        con.execute(
            """
            UPDATE leads
            SET status='new', screened_at=?, blocked_reason=NULL, updated_at=?
            WHERE tenant_id=? AND id=?
            """,
            (now, now, t, lead_id),
        )
        event_append(
            event_type="lead_screen_accepted",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_screen_accept",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "prev_status": str(row["status"] or ""),
                    "status": "new",
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def leads_screen_ignore(
    tenant_id: str,
    lead_id: str,
    actor_user_id: str | None = None,
    reason: str | None = None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    reason_norm = _validate_len(reason, MAX_BLOCKED_REASON)

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT status FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        _lead_require_claim_or_free_tx(con, t, lead_id, actor_user_id)
        now = _now_iso()
        blocked = reason_norm or "screening:ignored"
        con.execute(
            """
            UPDATE leads
            SET status='ignored', blocked_reason=?, screened_at=COALESCE(screened_at,?), updated_at=?
            WHERE tenant_id=? AND id=?
            """,
            (blocked, now, now, t, lead_id),
        )
        event_append(
            event_type="lead_screen_ignored",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_screen_ignore",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "prev_status": str(row["status"] or ""),
                    "status": "ignored",
                    "reason": "manual",
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def leads_block_sender(
    tenant_id: str,
    kind: str,
    value: str,
    actor_user_id: str | None,
    reason: str | None = None,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    kind_norm = legacy_core.normalize_component(kind).lower()
    if kind_norm not in BLOCKLIST_KINDS:
        raise ValueError("validation_error")

    if kind_norm in {"email", "domain"}:
        if kind_norm == "email":
            norm_value = normalize_email(value)
        else:
            norm_value = (value or "").strip().lower()
            if not norm_value or " " in norm_value or len(norm_value) > MAX_BLOCK_VALUE:
                raise ValueError("validation_error")
    else:
        norm_value = normalize_phone(value)

    if not norm_value:
        raise ValueError("validation_error")

    reason_norm = _validate_len(reason, MAX_BLOCKLIST_REASON)

    block_id = _new_id()

    def _tx(con: sqlite3.Connection) -> str:
        now = _now_iso()
        con.execute(
            """
            INSERT OR IGNORE INTO lead_blocklist(id, tenant_id, kind, value, reason, created_at, created_by)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                block_id,
                t,
                kind_norm,
                norm_value,
                reason_norm or None,
                now,
                actor_user_id,
            ),
        )
        row = con.execute(
            "SELECT id FROM lead_blocklist WHERE tenant_id=? AND kind=? AND value=? LIMIT 1",
            (t, kind_norm, norm_value),
        ).fetchone()
        out_id = str(row["id"] if row else block_id)
        event_append(
            event_type="lead_blocklist_added",
            entity_type="lead",
            entity_id=entity_id_int(out_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_block_sender",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {"kind": kind_norm, "value_present": True},
            },
            con=con,
        )
        return out_id

    return _run_write_txn(_tx)


def leads_set_priority(
    tenant_id: str,
    lead_id: str,
    priority: str,
    pinned: int,
    actor_user_id: str | None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    priority_norm = legacy_core.normalize_component(priority).lower()
    if priority_norm not in LEAD_PRIORITIES:
        raise ValueError("validation_error")
    if int(pinned) not in {0, 1}:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT priority, pinned FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        _lead_require_claim_or_free_tx(con, t, lead_id, actor_user_id)
        con.execute(
            "UPDATE leads SET priority=?, pinned=?, updated_at=? WHERE tenant_id=? AND id=?",
            (priority_norm, int(pinned), _now_iso(), t, lead_id),
        )
        event_append(
            event_type="lead_priority_changed",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_set_priority",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "prev_priority": str(row["priority"] or "normal"),
                    "priority": priority_norm,
                    "prev_pinned": int(row["pinned"] or 0),
                    "pinned": int(pinned),
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def leads_assign(
    tenant_id: str,
    lead_id: str,
    assigned_to: str | None,
    response_due: str | None,
    actor_user_id: str | None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    assigned_norm = _validate_len(assigned_to, MAX_ASSIGNED_TO)
    due_norm = _parse_response_due(response_due)

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT assigned_to, response_due FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        _lead_require_claim_or_free_tx(con, t, lead_id, actor_user_id)
        con.execute(
            "UPDATE leads SET assigned_to=?, response_due=?, updated_at=? WHERE tenant_id=? AND id=?",
            (assigned_norm or None, due_norm, _now_iso(), t, lead_id),
        )
        event_append(
            event_type="lead_assigned",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_assign",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "assigned_to_present": bool(assigned_norm),
                    "response_due_present": bool(due_norm),
                    "prev_assigned_to_present": bool(row["assigned_to"]),
                    "prev_response_due_present": bool(row["response_due"]),
                },
            },
            con=con,
        )

    _run_write_txn(_tx)


def leads_add_note(
    tenant_id: str,
    lead_id: str,
    note_text: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    note = _validate_len(note_text, MAX_NOTES)
    if not note:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT notes FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        prev = (row["notes"] or "").strip()
        next_note = note if not prev else f"{prev}\n- {note}"
        if len(next_note) > MAX_NOTES:
            raise ValueError("validation_error")
        con.execute(
            "UPDATE leads SET notes=?, updated_at=? WHERE tenant_id=? AND id=?",
            (next_note, _now_iso(), t, lead_id),
        )
        event_append(
            event_type="lead_note_added",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/leads_add_note",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {"lead_id": lead_id, "note_added": True},
            },
            con=con,
        )
        return None

    _run_write_txn(_tx)


def call_logs_create(
    tenant_id: str,
    lead_id: str | None,
    caller_name: str,
    caller_phone: str,
    direction: str,
    duration_seconds: int | None,
    notes: str | None,
    actor_user_id: str | None = None,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    dir_norm = legacy_core.normalize_component(direction).lower()
    if dir_norm not in CALL_DIRECTIONS:
        raise ValueError("validation_error")
    name_norm = _validate_len(caller_name, MAX_CONTACT_NAME)
    phone_norm = normalize_phone(caller_phone)
    notes_norm = _validate_len(notes, MAX_NOTES)
    call_id = _new_id()

    if duration_seconds is not None and int(duration_seconds) < 0:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> str:
        if lead_id:
            row = con.execute(
                "SELECT id FROM leads WHERE tenant_id=? AND id=?",
                (t, lead_id),
            ).fetchone()
            if not row:
                raise ValueError("not_found")
        con.execute(
            """
            INSERT INTO call_logs(
              id, tenant_id, lead_id, caller_name, caller_phone,
              direction, duration_seconds, notes, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                call_id,
                t,
                lead_id,
                name_norm,
                phone_norm,
                dir_norm,
                int(duration_seconds) if duration_seconds is not None else None,
                notes_norm or None,
                _now_iso(),
            ),
        )
        event_append(
            event_type="call_log_created",
            entity_type="call_log",
            entity_id=entity_id_int(call_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/call_logs_create",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "call_log_id": call_id,
                    "lead_id": lead_id,
                    "direction": dir_norm,
                    "duration_seconds": int(duration_seconds or 0),
                },
            },
            con=con,
        )
        return call_id

    return _run_write_txn(_tx)


def call_logs_list(tenant_id: str, lead_id: str | None = None) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    if lead_id:
        return _read_rows(
            """
            SELECT id, tenant_id, lead_id, caller_name, caller_phone, direction,
                   duration_seconds, notes, created_at
            FROM call_logs
            WHERE tenant_id=? AND lead_id=?
            ORDER BY created_at DESC, id DESC
            """,
            (t, lead_id),
        )
    return _read_rows(
        """
        SELECT id, tenant_id, lead_id, caller_name, caller_phone, direction,
               duration_seconds, notes, created_at
        FROM call_logs
        WHERE tenant_id=?
        ORDER BY created_at DESC, id DESC
        LIMIT 200
        """,
        (t,),
    )


def appointment_requests_create(
    tenant_id: str,
    lead_id: str,
    requested_date: str | None,
    notes: str | None,
    actor_user_id: str | None = None,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    due_norm = _parse_response_due(requested_date)
    notes_norm = _validate_len(notes, MAX_NOTES)
    req_id = _new_id()

    def _tx(con: sqlite3.Connection) -> str:
        row = con.execute(
            "SELECT id FROM leads WHERE tenant_id=? AND id=?",
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        now = _now_iso()
        con.execute(
            """
            INSERT INTO appointment_requests(
              id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                req_id,
                t,
                lead_id,
                due_norm,
                "pending",
                notes_norm or None,
                now,
                now,
            ),
        )
        event_append(
            event_type="appointment_request_created",
            entity_type="appointment_request",
            entity_id=entity_id_int(req_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/appointment_requests_create",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "appointment_request_id": req_id,
                    "lead_id": lead_id,
                    "status": "pending",
                    "requested_date_present": bool(due_norm),
                },
            },
            con=con,
        )
        return req_id

    return _run_write_txn(_tx)


def appointment_requests_update_status(
    tenant_id: str,
    req_id: str,
    status: str,
    actor_user_id: str | None = None,
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)
    st = legacy_core.normalize_component(status).lower()
    if st not in APPOINTMENT_STATUSES:
        raise ValueError("validation_error")

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT lead_id, status FROM appointment_requests WHERE tenant_id=? AND id=?",
            (t, req_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        prev = str(row["status"] or "")
        con.execute(
            "UPDATE appointment_requests SET status=?, updated_at=? WHERE tenant_id=? AND id=?",
            (st, _now_iso(), t, req_id),
        )
        event_append(
            event_type="appointment_request_status_updated",
            entity_type="appointment_request",
            entity_id=entity_id_int(req_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/appointment_requests_update_status",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "appointment_request_id": req_id,
                    "lead_id": str(row["lead_id"] or ""),
                    "prev_status": prev,
                    "status": st,
                },
            },
            con=con,
        )
        return None

    _run_write_txn(_tx)


def appointment_requests_get(tenant_id: str, req_id: str) -> dict[str, Any] | None:
    t = _tenant(tenant_id)
    rows = _read_rows(
        """
        SELECT id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
        FROM appointment_requests
        WHERE tenant_id=? AND id=?
        LIMIT 1
        """,
        (t, req_id),
    )
    return rows[0] if rows else None


def appointment_requests_list(
    tenant_id: str,
    lead_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    if lead_id:
        return _read_rows(
            """
            SELECT id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
            FROM appointment_requests
            WHERE tenant_id=? AND lead_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (t, lead_id, lim, off),
        )
    return _read_rows(
        """
        SELECT id, tenant_id, lead_id, requested_date, status, notes, created_at, updated_at
        FROM appointment_requests
        WHERE tenant_id=?
        ORDER BY updated_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (t, lim, off),
    )


def lead_timeline(tenant_id: str, lead_id: str, limit: int = 100) -> dict[str, Any]:
    t = _tenant(tenant_id)
    lim = max(1, min(int(limit), 500))
    lead_event_id = entity_id_int(lead_id)

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = legacy_core._db()  # type: ignore[attr-defined]
        try:
            events = con.execute(
                """
                SELECT id, ts, event_type, entity_type, entity_id, payload_json
                FROM events
                WHERE (entity_type='lead' AND entity_id=?)
                   OR (entity_type IN ('call_log','appointment_request') AND payload_json LIKE ?)
                ORDER BY ts DESC, id DESC
                LIMIT ?
                """,
                (lead_event_id, f'%"lead_id":"{lead_id}"%', lim),
            ).fetchall()
            calls = con.execute(
                """
                SELECT id, lead_id, caller_name, direction, duration_seconds, created_at
                FROM call_logs
                WHERE tenant_id=? AND lead_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (t, lead_id, lim),
            ).fetchall()
            appts = con.execute(
                """
                SELECT id, lead_id, requested_date, status, created_at, updated_at
                FROM appointment_requests
                WHERE tenant_id=? AND lead_id=?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (t, lead_id, lim),
            ).fetchall()
        finally:
            con.close()

    out_events: list[dict[str, Any]] = []
    for row in events:
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload_json") or "{}")
        except Exception:
            item["payload"] = {}
        out_events.append(item)

    return {
        "events": out_events,
        "call_logs": [dict(r) for r in calls],
        "appointment_requests": [dict(r) for r in appts],
    }


def lead_convert_to_deal_quote(
    tenant_id: str,
    lead_id: str,
    actor_user_id: str | None,
    mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    t = _tenant(tenant_id)
    data = mapping if isinstance(mapping, dict) else {}
    title_override = _validate_len(str(data.get("deal_title") or ""), MAX_DEAL_TITLE)
    customer_name_override = _validate_len(
        str(data.get("customer_name") or ""), MAX_CONTACT_NAME
    )
    use_subject_title = _as_bool(data.get("use_subject_title"))
    use_contact_name = _as_bool(data.get("use_contact_name"))

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT id, status, customer_id, subject, contact_name
            FROM leads
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (t, lead_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")

        _lead_require_claim_or_free_tx(con, t, lead_id, actor_user_id)

        now = _now_iso()
        prev_status = str(row["status"] or "")
        lead_subject = _validate_len(str(row["subject"] or ""), MAX_DEAL_TITLE)
        lead_contact_name = _validate_len(
            str(row["contact_name"] or ""), MAX_CONTACT_NAME
        )

        customer_id = str(row["customer_id"] or "")
        customer_created = False
        if not customer_id:
            customer_id = _new_id()
            customer_name = (
                customer_name_override
                or (lead_contact_name if use_contact_name else "")
                or f"Lead {lead_id[:8]}"
            )
            customer_name = _validate_len(customer_name, MAX_CONTACT_NAME)
            con.execute(
                """
                INSERT INTO customers(
                  id, tenant_id, name, vat_id, notes, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    customer_id,
                    t,
                    customer_name,
                    None,
                    "lead_conversion_v0",
                    now,
                    now,
                ),
            )
            customer_created = True
            event_append(
                event_type="crm_customer",
                entity_type="customer",
                entity_id=entity_id_int(customer_id),
                payload={
                    "schema_version": 1,
                    "source": "lead_intake/lead_convert_to_deal_quote",
                    "actor_user_id": actor_user_id,
                    "tenant_id": t,
                    "data": {"customer_id": customer_id, "lead_id": lead_id},
                },
                con=con,
            )

        deal_title = title_override or (lead_subject if use_subject_title else "")
        if not deal_title:
            deal_title = f"Lead {lead_id[:8]}"

        deal_id = _new_id()
        con.execute(
            """
            INSERT INTO deals(
              id, tenant_id, customer_id, title, stage, project_id,
              value_cents, currency, notes, probability, expected_close_date,
              created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                deal_id,
                t,
                customer_id,
                _validate_len(deal_title, MAX_DEAL_TITLE),
                "proposal",
                None,
                None,
                "EUR",
                "lead_conversion_v0",
                None,
                None,
                now,
                now,
            ),
        )

        quote_id = _new_id()
        quote_number = _next_quote_number(con, t)
        con.execute(
            """
            INSERT INTO quotes(
              id, tenant_id, customer_id, deal_id, status, currency,
              quote_number, subtotal_cents, tax_cents, tax_amount_cents, total_cents, notes, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                quote_id,
                t,
                customer_id,
                deal_id,
                "draft",
                "EUR",
                quote_number,
                0,
                0,
                0,
                0,
                "lead_conversion_v0",
                now,
                now,
            ),
        )

        con.execute(
            "UPDATE leads SET customer_id=?, status='qualified', updated_at=? WHERE tenant_id=? AND id=?",
            (customer_id, now, t, lead_id),
        )

        _insert_entity_link(
            con,
            tenant_id=t,
            left_type="deal",
            left_id=deal_id,
            right_type="lead",
            right_id=lead_id,
            link_type="converted_from",
            actor_user_id=actor_user_id,
            source="lead_intake/lead_convert_to_deal_quote",
        )
        _insert_entity_link(
            con,
            tenant_id=t,
            left_type="quote",
            left_id=quote_id,
            right_type="lead",
            right_id=lead_id,
            link_type="converted_from",
            actor_user_id=actor_user_id,
            source="lead_intake/lead_convert_to_deal_quote",
        )

        event_append(
            event_type="deal_created_from_lead",
            entity_type="deal",
            entity_id=entity_id_int(deal_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/lead_convert_to_deal_quote",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "deal_id": deal_id,
                    "quote_id": quote_id,
                    "customer_id": customer_id,
                    "customer_created": customer_created,
                    "use_subject_title": use_subject_title,
                    "use_contact_name": use_contact_name,
                },
            },
            con=con,
        )
        event_append(
            event_type="lead_converted",
            entity_type="lead",
            entity_id=entity_id_int(lead_id),
            payload={
                "schema_version": 1,
                "source": "lead_intake/lead_convert_to_deal_quote",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {
                    "lead_id": lead_id,
                    "deal_id": deal_id,
                    "quote_id": quote_id,
                    "customer_id": customer_id,
                    "status_from": prev_status,
                    "status_to": "qualified",
                },
            },
            con=con,
        )

        return {
            "lead_id": lead_id,
            "deal_id": deal_id,
            "quote_id": quote_id,
            "customer_id": customer_id,
            "customer_created": customer_created,
            "status": "qualified",
        }

    return _run_write_txn(_tx)


def _ics_safe_text(value: str, max_len: int = 180) -> str:
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value or "")
    text = text.replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"(?i)begin\s*:?[a-z]+", " ", text)
    text = re.sub(r"(?i)end\s*:?[a-z]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def appointment_request_to_ics(tenant_id: str, req_id: str) -> tuple[str, str]:
    item = appointment_requests_get(tenant_id, req_id)
    if not item:
        raise ValueError("not_found")

    lead = leads_get(tenant_id, str(item.get("lead_id") or "")) or {}
    now = datetime.now(UTC)
    dtstamp = now.strftime("%Y%m%dT%H%M%SZ")
    requested = item.get("requested_date")
    dtstart_line = ""
    if requested:
        try:
            dt = datetime.fromisoformat(str(requested))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            dtstart_line = (
                f"DTSTART:{dt.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}\\r\\n"
            )
        except Exception:
            pass
    if not dtstart_line:
        fallback = now + timedelta(days=1)
        dtstart_line = f"DTSTART:{fallback.strftime('%Y%m%dT%H%M%SZ')}\\r\\n"

    summary_src = str(
        lead.get("subject") or f"Lead {str(item.get('lead_id') or '')[:8]}"
    )
    summary = _ics_safe_text(f"Terminwunsch ({summary_src})")
    description = _ics_safe_text(f"Lead-ID: {item.get('lead_id') or ''}", max_len=500)
    ics = (
        "BEGIN:VCALENDAR\\r\\n"
        "VERSION:2.0\\r\\n"
        "PRODID:-//KUKANILEA//Lead Intake//DE\\r\\n"
        "BEGIN:VEVENT\\r\\n"
        f"UID:{_ics_safe_text(req_id, 80)}@kukanilea.local\\r\\n"
        f"DTSTAMP:{dtstamp}\\r\\n"
        f"{dtstart_line}"
        f"SUMMARY:{summary}\\r\\n"
        f"DESCRIPTION:{description}\\r\\n"
        "END:VEVENT\\r\\n"
        "END:VCALENDAR\\r\\n"
    )
    return ics, f"appointment_{req_id}.ics"
