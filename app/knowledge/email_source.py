from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from hashlib import sha256
from typing import Any

from flask import current_app, has_app_context

from app.core import logic as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

from .core import knowledge_policy_get

MAX_EMAIL_BYTES = 2 * 1024 * 1024
MAX_SUBJECT = 140
MAX_TITLE = 200
MAX_BODY = 20000
MAX_CHUNK = 2000
MAX_CHUNKS = 3

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
LONG_NUM_RE = re.compile(r"\b\d{7,}\b")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
DOMAIN_RE = re.compile(r"^[a-z0-9.-]{1,253}$")


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


def _db() -> sqlite3.Connection:
    return legacy_core._db()  # type: ignore[attr-defined]


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


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
        raise PermissionError("read_only")


def _clean(s: str | None, max_len: int) -> str:
    value = (s or "").replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > max_len:
        value = value[:max_len].rstrip()
    return value


def _redact_text(text: str | None, max_len: int) -> str:
    value = _clean(text, max_len * 2)
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = PHONE_RE.sub("[redacted-phone]", value)
    value = LONG_NUM_RE.sub("[redacted-number]", value)
    value = URL_RE.sub("[redacted-url]", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > max_len:
        value = value[:max_len].rstrip()
    return value


def _domain_only(addr: str | None) -> str | None:
    if not addr:
        return None
    value = (addr or "").strip().lower()
    if "@" not in value:
        return None
    domain = value.split("@", 1)[1].strip(". ")
    if not domain or not DOMAIN_RE.match(domain):
        return None
    return domain


def _parse_received_at(msg) -> str | None:
    raw_date = _clean(str(msg.get("date") or ""), 128)
    if not raw_date:
        return None
    try:
        parsed = parsedate_to_datetime(raw_date)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat(timespec="seconds")
    except Exception:
        return None


def _extract_body_and_attachment_flag(msg) -> tuple[str, int]:
    texts: list[str] = []
    has_attachments = 0
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get_content_disposition() or "").lower()
            if disp == "attachment" or part.get_filename():
                has_attachments = 1
                continue
            if ctype == "text/plain":
                try:
                    txt = part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    txt = payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
                if isinstance(txt, str) and txt.strip():
                    texts.append(txt)
    else:
        ctype = (msg.get_content_type() or "").lower()
        if ctype == "text/plain":
            try:
                txt = msg.get_content()
            except Exception:
                payload = msg.get_payload(decode=True) or b""
                txt = payload.decode(
                    msg.get_content_charset() or "utf-8", errors="replace"
                )
            if isinstance(txt, str) and txt.strip():
                texts.append(txt)
    body = "\n".join(texts)
    return body, has_attachments


def _policy_allows_email(policy_row: dict[str, Any]) -> bool:
    return bool(int(policy_row.get("allow_email", 0))) and bool(
        int(policy_row.get("allow_customer_pii", 0))
    )


def _insert_ingest_log(
    con: sqlite3.Connection,
    *,
    tenant_id: str,
    email_source_id: str,
    status: str,
    reason_code: str,
) -> None:
    con.execute(
        """
        INSERT INTO knowledge_email_ingest_log(
          id, tenant_id, email_source_id, status, reason_code, created_at
        ) VALUES (?,?,?,?,?,?)
        """,
        (_new_id(), tenant_id, email_source_id, status, reason_code, _now_iso()),
    )


def _upsert_fts_chunk(
    con: sqlite3.Connection, row_id: int, title: str, body: str, tags: str
) -> None:
    try:
        con.execute(
            "INSERT INTO knowledge_fts(rowid, title, body, tags) VALUES (?,?,?,?)",
            (row_id, title, body, tags),
        )
    except Exception:
        con.execute(
            "INSERT OR REPLACE INTO knowledge_fts_fallback(rowid, title, body, tags) VALUES (?,?,?,?)",
            (row_id, title, body, tags),
        )


def knowledge_email_ingest_eml(
    tenant_id: str,
    actor_user_id: str | None,
    eml_bytes: bytes,
    filename_hint: str | None = None,
) -> dict[str, Any]:
    _ensure_writable()
    tenant = _tenant(tenant_id)
    policy_row = knowledge_policy_get(tenant)
    if not _policy_allows_email(policy_row):
        raise ValueError("policy_blocked")

    if not eml_bytes:
        raise ValueError("empty_file")

    max_bytes = MAX_EMAIL_BYTES
    if has_app_context():
        try:
            max_bytes = int(
                current_app.config.get("KNOWLEDGE_EMAIL_MAX_BYTES", MAX_EMAIL_BYTES)
            )
        except Exception:
            max_bytes = MAX_EMAIL_BYTES
    if len(eml_bytes) > max_bytes:
        raise ValueError("payload_too_large")

    try:
        msg = BytesParser(policy=policy.default).parsebytes(eml_bytes)
    except Exception:
        raise ValueError("parse_error")

    content_sha = sha256(eml_bytes).hexdigest()
    subject = _redact_text(str(msg.get("subject") or ""), MAX_SUBJECT)
    title = _clean(subject or "(no subject)", MAX_TITLE)
    from_domain = None
    from_addr = getaddresses([str(msg.get("from") or "")])
    if from_addr:
        from_domain = _domain_only(from_addr[0][1])

    to_domains = []
    for _name, addr in getaddresses([str(msg.get("to") or "")]):
        dom = _domain_only(addr)
        if dom:
            to_domains.append(dom)
    to_domains = sorted(set(to_domains))

    received_at = _parse_received_at(msg)
    body_raw, has_attachments = _extract_body_and_attachment_flag(msg)
    body_redacted = _redact_text(body_raw, MAX_BODY)

    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> dict[str, Any]:
        row = con.execute(
            "SELECT id FROM knowledge_email_sources WHERE tenant_id=? AND content_sha256=? LIMIT 1",
            (tenant, content_sha),
        ).fetchone()
        created_new = row is None
        if created_new:
            source_id = _new_id()
            con.execute(
                """
                INSERT INTO knowledge_email_sources(
                  id, tenant_id, content_sha256, received_at, subject_redacted,
                  from_domain, to_domains_json, has_attachments, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    source_id,
                    tenant,
                    content_sha,
                    received_at,
                    title,
                    from_domain,
                    json.dumps(to_domains, separators=(",", ":"), sort_keys=True),
                    int(has_attachments),
                    now,
                    now,
                ),
            )
        else:
            source_id = str(row["id"])
            con.execute(
                "UPDATE knowledge_email_sources SET updated_at=? WHERE tenant_id=? AND id=?",
                (now, tenant, source_id),
            )

        chunks_created = 0
        if created_new:
            if len(body_redacted) < 50:
                _insert_ingest_log(
                    con,
                    tenant_id=tenant,
                    email_source_id=source_id,
                    status="redacted_empty",
                    reason_code="content_too_short",
                )
            else:
                segments = [
                    body_redacted[i : i + MAX_CHUNK]
                    for i in range(0, len(body_redacted), MAX_CHUNK)
                ]
                for seg in segments[:MAX_CHUNKS]:
                    chunk_id = _new_id()
                    source_ref = f"email:{source_id}"
                    c_hash = sha256(seg.encode("utf-8")).hexdigest()
                    cur = con.execute(
                        """
                        INSERT OR IGNORE INTO knowledge_chunks(
                          chunk_id, tenant_id, owner_user_id, source_type, source_ref,
                          title, body, tags, content_hash, is_redacted, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            chunk_id,
                            tenant,
                            actor_user_id or None,
                            "email",
                            source_ref,
                            title,
                            seg,
                            "email,ingested",
                            c_hash,
                            1,
                            now,
                            now,
                        ),
                    )
                    if int(cur.rowcount or 0) > 0:
                        chunks_created += 1
                        row2 = con.execute(
                            "SELECT id FROM knowledge_chunks WHERE tenant_id=? AND chunk_id=? LIMIT 1",
                            (tenant, chunk_id),
                        ).fetchone()
                        if row2:
                            _upsert_fts_chunk(
                                con,
                                int(row2["id"]),
                                title,
                                seg,
                                "email,ingested",
                            )

                _insert_ingest_log(
                    con,
                    tenant_id=tenant,
                    email_source_id=source_id,
                    status="ok",
                    reason_code="ingested",
                )

                event_append(
                    event_type="knowledge_email_ingested",
                    entity_type="knowledge_email",
                    entity_id=entity_id_int(source_id),
                    payload={
                        "schema_version": 1,
                        "source": "knowledge/email_ingest",
                        "actor_user_id": actor_user_id,
                        "tenant_id": tenant,
                        "data": {
                            "source_id": source_id,
                            "content_sha256_prefix": content_sha[:12],
                            "chunks_created": int(chunks_created),
                            "has_attachments": int(has_attachments),
                            "filename_present": bool(filename_hint),
                        },
                    },
                    con=con,
                )
        else:
            _insert_ingest_log(
                con,
                tenant_id=tenant,
                email_source_id=source_id,
                status="ok",
                reason_code="dedup",
            )

        return {
            "source_id": source_id,
            "tenant_id": tenant,
            "dedup": not created_new,
            "chunks_created": int(chunks_created),
            "has_attachments": int(has_attachments),
            "subject_redacted": title,
            "received_at": received_at,
        }

    return _run_write_txn(_tx)


def knowledge_email_sources_list(
    tenant_id: str, page: int = 1, page_size: int = 25
) -> tuple[list[dict[str, Any]], int]:
    tenant = _tenant(tenant_id)
    p = max(1, int(page))
    ps = max(1, min(int(page_size), 100))
    offset = (p - 1) * ps
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            rows = con.execute(
                """
                SELECT id, content_sha256, received_at, subject_redacted, from_domain,
                       to_domains_json, has_attachments, created_at, updated_at
                FROM knowledge_email_sources
                WHERE tenant_id=?
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (tenant, ps, offset),
            ).fetchall()
            total_row = con.execute(
                "SELECT COUNT(*) AS n FROM knowledge_email_sources WHERE tenant_id=?",
                (tenant,),
            ).fetchone()
            total = int(total_row["n"] if total_row else 0)
            out: list[dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                try:
                    item["to_domains"] = json.loads(item.get("to_domains_json") or "[]")
                except Exception:
                    item["to_domains"] = []
                out.append(item)
            return out, total
        finally:
            con.close()
