from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from app import core as core
from app.config import Config
from app.core.upload_pipeline import MAX_FILE_SIZE
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.knowledge import knowledge_redact_text

MAIL_ATTACHMENT_TENANT_QUOTA_BYTES = int(
    os.environ.get("KUKANILEA_MAIL_ATTACHMENT_TENANT_QUOTA_BYTES", str(100 * 1024 * 1024))
)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as exc:  # pragma: no cover
    raise RuntimeError("cryptography_required_for_postfach") from exc


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _email_key() -> bytes:
    raw = str(os.environ.get("EMAIL_ENCRYPTION_KEY", "") or "").strip()
    if not raw:
        raise ValueError("email_encryption_key_missing")
    if raw.startswith("base64:"):
        decoded = base64.urlsafe_b64decode(raw.split(":", 1)[1].encode("utf-8"))
        if len(decoded) in {16, 24, 32}:
            return decoded
    try:
        maybe_hex = bytes.fromhex(raw)
        if len(maybe_hex) in {16, 24, 32}:
            return maybe_hex
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def email_encryption_ready() -> bool:
    try:
        _email_key()
        return True
    except Exception:
        return False


def encrypt_text(value: str) -> str:
    key = _email_key()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    encrypted = aes.encrypt(nonce, (value or "").encode("utf-8"), b"kukanilea-postfach")
    packed = nonce + encrypted
    return "aesgcm:" + base64.urlsafe_b64encode(packed).decode("ascii")


def decrypt_text(value: str) -> str:
    raw = str(value or "")
    if not raw.startswith("aesgcm:"):
        raise ValueError("invalid_ciphertext")
    packed = base64.urlsafe_b64decode(raw.split(":", 1)[1].encode("ascii"))
    nonce = packed[:12]
    ciphertext = packed[12:]
    aes = AESGCM(_email_key())
    plain = aes.decrypt(nonce, ciphertext, b"kukanilea-postfach")
    return plain.decode("utf-8")


def encrypt_bytes(value: bytes) -> str:
    key = _email_key()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    encrypted = aes.encrypt(nonce, value or b"", b"kukanilea-postfach-bytes")
    return "aesgcm:" + base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")


def decrypt_bytes(value: str) -> bytes:
    raw = str(value or "")
    if not raw.startswith("aesgcm:"):
        raise ValueError("invalid_ciphertext")
    packed = base64.urlsafe_b64decode(raw.split(":", 1)[1].encode("ascii"))
    nonce = packed[:12]
    ciphertext = packed[12:]
    aes = AESGCM(_email_key())
    return bytes(aes.decrypt(nonce, ciphertext, b"kukanilea-postfach-bytes"))


def _table_columns(con: sqlite3.Connection, table_name: str) -> set[str]:
    sql = "PRAGMA table_info(%s)" % table_name
    rows = con.execute(sql).fetchall()
    return {str(r["name"]) for r in rows}


def _ensure_column(con: sqlite3.Connection, table: str, column_def: str) -> None:
    col_name = str(column_def.split()[0]).strip()
    if col_name in _table_columns(con, table):
        return
    sql = "ALTER TABLE %s ADD COLUMN %s" % (table, column_def)
    con.execute(sql)


def _table_exists(con: sqlite3.Connection, table_name: str) -> bool:
    row = con.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name=?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return bool(row)


def _normalize_email_candidates(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        lowered = str(value or "").strip().lower()
        if not lowered or "@" not in lowered:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(lowered)
    return out


def _safe_attachment_filename(name: str, *, fallback: str) -> str:
    raw = str(name or "").strip().replace("\x00", "")
    base = Path(raw).name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not clean:
        return fallback
    return clean[:180]


def _migrate_legacy_account_secrets(con: sqlite3.Connection) -> int:
    """
    Backfill legacy plaintext secrets into AES-GCM encrypted payloads.
    The migration is best effort and only runs when EMAIL_ENCRYPTION_KEY is available.
    """
    if not email_encryption_ready():
        return 0

    rows = con.execute(
        """
        SELECT id, encrypted_secret
        FROM mailbox_accounts
        WHERE encrypted_secret IS NOT NULL AND TRIM(encrypted_secret) != ''
        """
    ).fetchall()
    migrated = 0
    now = _now_iso()
    for row in rows:
        account_id = str(row["id"] or "")
        current = str(row["encrypted_secret"] or "")
        if not account_id or not current or current.startswith("aesgcm:"):
            continue
        try:
            encrypted = encrypt_text(current)
        except Exception:
            continue
        con.execute(
            """
            UPDATE mailbox_accounts
            SET encrypted_secret=?, updated_at=?
            WHERE id=?
            """,
            (encrypted, now, account_id),
        )
        migrated += 1
    return migrated


def ensure_postfach_schema(db_path: Path) -> None:
    con = _db(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_accounts(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              label TEXT NOT NULL,
              imap_host TEXT NOT NULL,
              imap_port INTEGER NOT NULL DEFAULT 993,
              imap_username TEXT NOT NULL,
              smtp_host TEXT NOT NULL,
              smtp_port INTEGER NOT NULL DEFAULT 465,
              smtp_username TEXT NOT NULL,
              smtp_use_ssl INTEGER NOT NULL DEFAULT 1,
              encrypted_secret TEXT NOT NULL,
              sync_cursor TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_accounts_tenant ON mailbox_accounts(tenant_id, updated_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_threads(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              account_id TEXT NOT NULL,
              subject_redacted TEXT NOT NULL,
              participants_redacted TEXT NOT NULL,
              thread_key TEXT NOT NULL,
              last_message_at TEXT,
              message_count INTEGER NOT NULL DEFAULT 0,
              status TEXT NOT NULL DEFAULT 'open',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(account_id, thread_key),
              FOREIGN KEY(account_id) REFERENCES mailbox_accounts(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_threads_tenant ON mailbox_threads(tenant_id, account_id, last_message_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_messages(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              account_id TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              direction TEXT NOT NULL,
              message_id_header TEXT,
              content_hash TEXT NOT NULL,
              in_reply_to TEXT,
              references_header TEXT,
              from_redacted TEXT NOT NULL,
              to_redacted TEXT NOT NULL,
              subject_redacted TEXT NOT NULL,
              redacted_text TEXT NOT NULL,
              raw_eml_blob TEXT,
              has_attachments INTEGER NOT NULL DEFAULT 0,
              received_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(account_id, message_id_header),
              UNIQUE(account_id, content_hash),
              FOREIGN KEY(account_id) REFERENCES mailbox_accounts(id) ON DELETE CASCADE,
              FOREIGN KEY(thread_id) REFERENCES mailbox_threads(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_messages_thread ON mailbox_messages(tenant_id, thread_id, created_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_attachments(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              message_id TEXT NOT NULL,
              filename_redacted TEXT NOT NULL,
              mime_type TEXT NOT NULL,
              size_bytes INTEGER NOT NULL DEFAULT 0,
              content_ref TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(message_id) REFERENCES mailbox_messages(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_attachments_msg ON mailbox_attachments(tenant_id, message_id)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_drafts(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              account_id TEXT NOT NULL,
              thread_id TEXT,
              to_redacted TEXT NOT NULL,
              subject_redacted TEXT NOT NULL,
              body_redacted TEXT NOT NULL,
              to_encrypted TEXT NOT NULL,
              subject_encrypted TEXT NOT NULL,
              body_encrypted TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'draft',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              sent_at TEXT,
              FOREIGN KEY(account_id) REFERENCES mailbox_accounts(id) ON DELETE CASCADE,
              FOREIGN KEY(thread_id) REFERENCES mailbox_threads(id) ON DELETE SET NULL
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_drafts_tenant ON mailbox_drafts(tenant_id, status, updated_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_links(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(thread_id, entity_type, entity_id),
              FOREIGN KEY(thread_id) REFERENCES mailbox_threads(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_links_thread ON mailbox_links(tenant_id, thread_id, created_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_oauth_tokens(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              account_id TEXT NOT NULL,
              provider TEXT NOT NULL,
              token_type TEXT NOT NULL DEFAULT 'Bearer',
              access_token_encrypted TEXT NOT NULL,
              refresh_token_encrypted TEXT,
              expires_at TEXT,
              scopes_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(tenant_id, account_id, provider),
              FOREIGN KEY(account_id) REFERENCES mailbox_accounts(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_oauth_tokens_account ON mailbox_oauth_tokens(tenant_id, account_id, updated_at DESC)"
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mailbox_intake_artifacts(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              thread_id TEXT NOT NULL,
              schema_name TEXT NOT NULL,
              fields_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(tenant_id, thread_id, schema_name),
              FOREIGN KEY(thread_id) REFERENCES mailbox_threads(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mailbox_intake_artifacts_thread ON mailbox_intake_artifacts(tenant_id, thread_id, updated_at DESC)"
        )
        _ensure_column(
            con, "mailbox_accounts", "auth_mode TEXT NOT NULL DEFAULT 'password'"
        )
        _ensure_column(con, "mailbox_accounts", "oauth_provider TEXT")
        _ensure_column(
            con,
            "mailbox_accounts",
            "oauth_status TEXT NOT NULL DEFAULT 'not_connected'",
        )
        _ensure_column(con, "mailbox_accounts", "oauth_last_error TEXT")
        _ensure_column(con, "mailbox_accounts", "oauth_scopes TEXT")
        _ensure_column(con, "mailbox_accounts", "last_sync_at TEXT")
        _ensure_column(con, "mailbox_accounts", "last_sync_status TEXT")
        _ensure_column(con, "mailbox_accounts", "last_sync_error TEXT")
        _ensure_column(
            con, "mailbox_accounts", "last_sync_imported INTEGER NOT NULL DEFAULT 0"
        )
        _ensure_column(
            con, "mailbox_accounts", "last_sync_duplicates INTEGER NOT NULL DEFAULT 0"
        )
        _migrate_legacy_account_secrets(con)
        con.commit()
    finally:
        con.close()


def _event(
    *,
    event_type: str,
    entity_type: str,
    entity_text_id: str,
    tenant_id: str,
    payload: dict[str, Any],
) -> None:
    try:
        event_append(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id_int(entity_text_id),
            payload={
                "schema_version": 1,
                "tenant_id": tenant_id,
                "payload": payload,
            },
        )
    except Exception:
        return


def create_account(
    db_path: Path,
    *,
    tenant_id: str,
    label: str,
    imap_host: str,
    imap_port: int,
    imap_username: str,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_use_ssl: bool,
    secret_plain: str,
    auth_mode: str = "password",
    oauth_provider: str | None = None,
) -> str:
    ensure_postfach_schema(db_path)
    mode = str(auth_mode or "password").strip().lower()
    provider = str(oauth_provider or "").strip().lower() or None
    if mode not in {"password", "oauth_google", "oauth_microsoft"}:
        raise ValueError("validation_error")
    if mode == "password":
        if not str(secret_plain or "").strip():
            raise ValueError("account_secret_required")
        encrypted_secret = encrypt_text(secret_plain)
    else:
        encrypted_secret = encrypt_text("__oauth__")
        if not provider:
            provider = "google" if mode == "oauth_google" else "microsoft"

    now = _now_iso()
    account_id = uuid.uuid4().hex
    con = _db(db_path)
    try:
        con.execute(
            """
            INSERT INTO mailbox_accounts(
              id, tenant_id, label, imap_host, imap_port, imap_username,
              smtp_host, smtp_port, smtp_username, smtp_use_ssl,
              encrypted_secret, auth_mode, oauth_provider, oauth_status, sync_cursor,
              created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                account_id,
                tenant_id,
                label.strip(),
                imap_host.strip(),
                int(imap_port),
                imap_username.strip(),
                smtp_host.strip() or imap_host.strip(),
                int(smtp_port),
                smtp_username.strip() or imap_username.strip(),
                1 if smtp_use_ssl else 0,
                encrypted_secret,
                mode,
                provider,
                "not_connected" if mode != "password" else "n/a",
                None,
                now,
                now,
            ),
        )
        con.commit()
    finally:
        con.close()

    _event(
        event_type="mailbox_account_created",
        entity_type="mailbox_account",
        entity_text_id=account_id,
        tenant_id=tenant_id,
        payload={
            "account_id": account_id,
            "imap_host": imap_host.strip(),
            "smtp_host": (smtp_host.strip() or imap_host.strip()),
            "auth_mode": mode,
            "oauth_provider": provider,
        },
    )
    return account_id


def list_accounts(db_path: Path, tenant_id: str) -> list[dict[str, Any]]:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, tenant_id, label, imap_host, imap_port, imap_username,
                   smtp_host, smtp_port, smtp_username, smtp_use_ssl,
                   auth_mode, oauth_provider, oauth_status, oauth_last_error, oauth_scopes,
                   sync_cursor, last_sync_at, last_sync_status, last_sync_error,
                   last_sync_imported, last_sync_duplicates, created_at, updated_at
            FROM mailbox_accounts
            WHERE tenant_id=?
            ORDER BY updated_at DESC
            """,
            (tenant_id,),
        ).fetchall()
        out = [dict(r) for r in rows]
        for row in out:
            row["imap_username_redacted"] = knowledge_redact_text(
                str(row.get("imap_username") or ""), max_len=120
            )
            row["smtp_username_redacted"] = knowledge_redact_text(
                str(row.get("smtp_username") or ""), max_len=120
            )
            row["oauth_last_error"] = knowledge_redact_text(
                str(row.get("oauth_last_error") or ""), max_len=180
            )
            row["last_sync_error"] = knowledge_redact_text(
                str(row.get("last_sync_error") or ""), max_len=180
            )
            raw_scopes = str(row.get("oauth_scopes") or "").strip()
            scopes_list: list[str] = []
            if raw_scopes:
                try:
                    parsed = json.loads(raw_scopes)
                    if isinstance(parsed, list):
                        scopes_list = [str(s) for s in parsed if str(s).strip()]
                except Exception:
                    scopes_list = []
            row["oauth_scopes_list"] = scopes_list
            row.pop("imap_username", None)
            row.pop("smtp_username", None)
        return out
    finally:
        con.close()


def get_account(
    db_path: Path, tenant_id: str, account_id: str
) -> dict[str, Any] | None:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        row = con.execute(
            """
            SELECT *
            FROM mailbox_accounts
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant_id, account_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def update_account_sync_cursor(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    sync_cursor: str,
) -> None:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        con.execute(
            """
            UPDATE mailbox_accounts
            SET sync_cursor=?, updated_at=?
            WHERE tenant_id=? AND id=?
            """,
            (str(sync_cursor or ""), _now_iso(), tenant_id, account_id),
        )
        con.commit()
    finally:
        con.close()


def update_account_sync_report(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    ok: bool,
    imported: int,
    duplicates: int,
    error_reason: str = "",
) -> None:
    ensure_postfach_schema(db_path)
    now = _now_iso()
    con = _db(db_path)
    try:
        con.execute(
            """
            UPDATE mailbox_accounts
            SET last_sync_at=?,
                last_sync_status=?,
                last_sync_error=?,
                last_sync_imported=?,
                last_sync_duplicates=?,
                updated_at=?
            WHERE tenant_id=? AND id=?
            """,
            (
                now,
                "ok" if ok else "error",
                str(error_reason or "").strip()[:240] or None,
                int(imported or 0),
                int(duplicates or 0),
                now,
                tenant_id,
                account_id,
            ),
        )
        con.commit()
    finally:
        con.close()


def set_account_oauth_state(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    oauth_status: str,
    oauth_last_error: str = "",
    oauth_provider: str | None = None,
    oauth_scopes: list[str] | None = None,
) -> None:
    ensure_postfach_schema(db_path)
    now = _now_iso()
    con = _db(db_path)
    try:
        con.execute(
            """
            UPDATE mailbox_accounts
            SET oauth_status=?,
                oauth_last_error=?,
                oauth_provider=COALESCE(?, oauth_provider),
                oauth_scopes=COALESCE(?, oauth_scopes),
                updated_at=?
            WHERE tenant_id=? AND id=?
            """,
            (
                str(oauth_status or "").strip() or "not_connected",
                str(oauth_last_error or "").strip()[:240] or None,
                str(oauth_provider or "").strip() or None,
                json.dumps(list(oauth_scopes or []), ensure_ascii=False),
                now,
                tenant_id,
                account_id,
            ),
        )
        con.commit()
    finally:
        con.close()


def save_oauth_token(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    provider: str,
    access_token: str,
    refresh_token: str,
    expires_at: str,
    scopes: list[str],
    token_type: str = "Bearer",
) -> str:
    ensure_postfach_schema(db_path)
    token_id = uuid.uuid4().hex
    now = _now_iso()
    con = _db(db_path)
    try:
        con.execute(
            """
            INSERT INTO mailbox_oauth_tokens(
              id, tenant_id, account_id, provider, token_type,
              access_token_encrypted, refresh_token_encrypted, expires_at, scopes_json,
              created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id, account_id, provider) DO UPDATE SET
              token_type=excluded.token_type,
              access_token_encrypted=excluded.access_token_encrypted,
              refresh_token_encrypted=CASE
                WHEN excluded.refresh_token_encrypted IS NOT NULL
                THEN excluded.refresh_token_encrypted
                ELSE mailbox_oauth_tokens.refresh_token_encrypted
              END,
              expires_at=excluded.expires_at,
              scopes_json=excluded.scopes_json,
              updated_at=excluded.updated_at
            """,
            (
                token_id,
                tenant_id,
                account_id,
                str(provider or "").strip().lower(),
                str(token_type or "Bearer").strip(),
                encrypt_text(access_token),
                encrypt_text(refresh_token)
                if str(refresh_token or "").strip()
                else None,
                str(expires_at or "").strip() or None,
                json.dumps(list(scopes or []), ensure_ascii=False),
                now,
                now,
            ),
        )
        con.commit()
    finally:
        con.close()
    return token_id


def get_oauth_token(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    provider: str | None = None,
) -> dict[str, Any] | None:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        if provider:
            row = con.execute(
                """
                SELECT *
                FROM mailbox_oauth_tokens
                WHERE tenant_id=? AND account_id=? AND provider=?
                LIMIT 1
                """,
                (tenant_id, account_id, str(provider or "").strip().lower()),
            ).fetchone()
        else:
            row = con.execute(
                """
                SELECT *
                FROM mailbox_oauth_tokens
                WHERE tenant_id=? AND account_id=?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (tenant_id, account_id),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
    finally:
        con.close()

    access = decrypt_text(str(data.get("access_token_encrypted") or ""))
    refresh_enc = str(data.get("refresh_token_encrypted") or "")
    refresh = decrypt_text(refresh_enc) if refresh_enc else ""
    scopes = []
    try:
        raw_scopes = json.loads(str(data.get("scopes_json") or "[]"))
        if isinstance(raw_scopes, list):
            scopes = [str(s) for s in raw_scopes if str(s).strip()]
    except Exception:
        scopes = []

    return {
        "id": str(data.get("id") or ""),
        "tenant_id": str(data.get("tenant_id") or ""),
        "account_id": str(data.get("account_id") or ""),
        "provider": str(data.get("provider") or ""),
        "token_type": str(data.get("token_type") or "Bearer"),
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": str(data.get("expires_at") or ""),
        "scopes": scopes,
    }


def oauth_token_expired(expires_at: str, *, skew_seconds: int = 60) -> bool:
    raw = str(expires_at or "").strip()
    if not raw:
        return True
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
    except Exception:
        return True
    return datetime.now(UTC).timestamp() >= (dt.timestamp() - skew_seconds)


def clear_oauth_token(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    provider: str | None = None,
) -> None:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        if provider:
            con.execute(
                """
                DELETE FROM mailbox_oauth_tokens
                WHERE tenant_id=? AND account_id=? AND provider=?
                """,
                (tenant_id, account_id, str(provider or "").strip().lower()),
            )
        else:
            con.execute(
                "DELETE FROM mailbox_oauth_tokens WHERE tenant_id=? AND account_id=?",
                (tenant_id, account_id),
            )
        con.commit()
    finally:
        con.close()


def decrypt_account_secret(account: dict[str, Any]) -> str:
    encrypted_secret = str(account.get("encrypted_secret") or "")
    if not encrypted_secret:
        raise ValueError("account_secret_missing")
    return decrypt_text(encrypted_secret)


def _normalize_subject(subject: str) -> str:
    raw = str(subject or "").strip().lower()
    return re.sub(r"^(re|fwd?|aw)\s*:\s*", "", raw).strip()


def _thread_key(subject_redacted: str, participants_redacted: str) -> str:
    base = f"{_normalize_subject(subject_redacted)}|{participants_redacted.strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _extract_message_ids(header_value: str | None) -> list[str]:
    raw = str(header_value or "")
    out = re.findall(r"<[^>]+>", raw)
    if out:
        return [x.strip() for x in out]
    parts = [p.strip() for p in raw.split() if p.strip()]
    return parts[:20]


def _resolve_thread_id(
    con: sqlite3.Connection,
    *,
    tenant_id: str,
    account_id: str,
    subject_redacted: str,
    participants_redacted: str,
    in_reply_to: str | None,
    references_header: str | None,
) -> str:
    candidates = _extract_message_ids(in_reply_to) + _extract_message_ids(
        references_header
    )
    for msgid in candidates:
        row = con.execute(
            """
            SELECT thread_id
            FROM mailbox_messages
            WHERE tenant_id=? AND account_id=? AND message_id_header=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (tenant_id, account_id, msgid),
        ).fetchone()
        if row and row["thread_id"]:
            return str(row["thread_id"])

    key = _thread_key(subject_redacted, participants_redacted)
    existing = con.execute(
        """
        SELECT id
        FROM mailbox_threads
        WHERE tenant_id=? AND account_id=? AND thread_key=?
        LIMIT 1
        """,
        (tenant_id, account_id, key),
    ).fetchone()
    if existing and existing["id"]:
        return str(existing["id"])

    thread_id = uuid.uuid4().hex
    now = _now_iso()
    con.execute(
        """
        INSERT INTO mailbox_threads(
          id, tenant_id, account_id, subject_redacted, participants_redacted,
          thread_key, last_message_at, message_count, status, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            thread_id,
            tenant_id,
            account_id,
            subject_redacted,
            participants_redacted,
            key,
            now,
            0,
            "open",
            now,
            now,
        ),
    )
    return thread_id


def store_message(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    direction: str,
    message_id_header: str | None,
    in_reply_to: str | None,
    references_header: str | None,
    from_value: str,
    to_value: str,
    subject_value: str,
    body_value: str,
    raw_eml: bytes | None,
    has_attachments: bool,
    received_at: str,
) -> dict[str, Any]:
    ensure_postfach_schema(db_path)

    safe_direction = str(direction or "inbound").strip().lower()
    if safe_direction not in {"inbound", "outbound"}:
        raise ValueError("validation_error")

    message_id_clean = str(message_id_header or "").strip() or None
    from_redacted = knowledge_redact_text(from_value, max_len=220)
    to_redacted = knowledge_redact_text(to_value, max_len=220)
    subject_redacted = knowledge_redact_text(subject_value, max_len=260)
    body_redacted = knowledge_redact_text(body_value, max_len=12000)
    participants_redacted = knowledge_redact_text(
        f"{from_redacted} {to_redacted}", max_len=260
    )
    content_hash = hashlib.sha256(
        (f"{message_id_clean or ''}|{subject_redacted}|{body_redacted}").encode()
    ).hexdigest()

    raw_eml_blob = None
    if raw_eml:
        raw_eml_blob = encrypt_bytes(raw_eml)

    now = _now_iso()
    con = _db(db_path)
    try:
        if message_id_clean:
            existing = con.execute(
                """
                SELECT id, thread_id
                FROM mailbox_messages
                WHERE tenant_id=? AND account_id=? AND message_id_header=?
                LIMIT 1
                """,
                (tenant_id, account_id, message_id_clean),
            ).fetchone()
            if existing:
                return {
                    "ok": True,
                    "duplicate": True,
                    "message_id": str(existing["id"]),
                    "thread_id": str(existing["thread_id"]),
                }

        existing_hash = con.execute(
            """
            SELECT id, thread_id
            FROM mailbox_messages
            WHERE tenant_id=? AND account_id=? AND content_hash=?
            LIMIT 1
            """,
            (tenant_id, account_id, content_hash),
        ).fetchone()
        if existing_hash:
            return {
                "ok": True,
                "duplicate": True,
                "message_id": str(existing_hash["id"]),
                "thread_id": str(existing_hash["thread_id"]),
            }

        thread_id = _resolve_thread_id(
            con,
            tenant_id=tenant_id,
            account_id=account_id,
            subject_redacted=subject_redacted,
            participants_redacted=participants_redacted,
            in_reply_to=in_reply_to,
            references_header=references_header,
        )

        message_id = uuid.uuid4().hex
        con.execute(
            """
            INSERT INTO mailbox_messages(
              id, tenant_id, account_id, thread_id, direction,
              message_id_header, content_hash, in_reply_to, references_header,
              from_redacted, to_redacted, subject_redacted,
              redacted_text, raw_eml_blob, has_attachments,
              received_at, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                message_id,
                tenant_id,
                account_id,
                thread_id,
                safe_direction,
                message_id_clean,
                content_hash,
                str(in_reply_to or "").strip() or None,
                str(references_header or "").strip() or None,
                from_redacted,
                to_redacted,
                subject_redacted,
                body_redacted,
                raw_eml_blob,
                1 if has_attachments else 0,
                str(received_at or now),
                now,
                now,
            ),
        )
        con.execute(
            """
            UPDATE mailbox_threads
            SET last_message_at=?,
                message_count=(
                  SELECT COUNT(*)
                  FROM mailbox_messages m
                  WHERE m.tenant_id=mailbox_threads.tenant_id
                    AND m.thread_id=mailbox_threads.id
                ),
                updated_at=?
            WHERE tenant_id=? AND id=?
            """,
            (str(received_at or now), now, tenant_id, thread_id),
        )
        con.commit()
    finally:
        con.close()

    _event(
        event_type=(
            "mailbox_message_received"
            if safe_direction == "inbound"
            else "mailbox_message_sent"
        ),
        entity_type="mailbox_thread",
        entity_text_id=thread_id,
        tenant_id=tenant_id,
        payload={
            "account_id": account_id,
            "thread_id": thread_id,
            "message_id": message_id,
            "direction": safe_direction,
            "has_attachments": bool(has_attachments),
        },
    )

    return {
        "ok": True,
        "duplicate": False,
        "message_id": message_id,
        "thread_id": thread_id,
    }


def store_message_attachment(
    db_path: Path,
    *,
    tenant_id: str,
    message_id: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    content_ref: dict[str, Any] | None = None,
) -> str:
    ensure_postfach_schema(db_path)
    attachment_id = uuid.uuid4().hex
    now = _now_iso()
    con = _db(db_path)
    try:
        con.execute(
            """
            INSERT INTO mailbox_attachments(
              id, tenant_id, message_id, filename_redacted, mime_type, size_bytes, content_ref, created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                attachment_id,
                tenant_id,
                message_id,
                knowledge_redact_text(str(filename or ""), max_len=220),
                str(mime_type or "application/octet-stream").strip().lower()[:120],
                max(0, int(size_bytes or 0)),
                json.dumps(content_ref or {}, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
        con.commit()
    finally:
        con.close()
    return attachment_id


def ingest_message_attachments(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    message_id: str,
    attachments: list[dict[str, Any]],
) -> dict[str, Any]:
    ensure_postfach_schema(db_path)
    tenant_key = str(tenant_id or "default")
    base_dir = (
        Config.USER_DATA_ROOT
        / "mail_attachments"
        / tenant_key
        / str(account_id or "unknown")
        / str(message_id or "unknown")
    )
    quarantine_dir = Config.USER_DATA_ROOT / "mail_quarantine"
    tenant_dir = Config.USER_DATA_ROOT / "mail_attachments" / tenant_key
    base_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    accepted = 0
    rejected = 0
    quarantined = 0
    errors = 0
    attachment_ids: list[str] = []
    tenant_usage_bytes = sum(
        path.stat().st_size for path in tenant_dir.rglob("*") if path.is_file()
    )

    for idx, attachment in enumerate(attachments, start=1):
        filename = _safe_attachment_filename(
            str(attachment.get("filename") or ""),
            fallback=f"attachment_{idx:03d}.bin",
        )
        mime_type = str(attachment.get("mime_type") or "application/octet-stream")
        payload = bytes(attachment.get("content_bytes") or b"")
        size_bytes = int(attachment.get("size_bytes") or len(payload))
        payload_size_bytes = max(0, len(payload), size_bytes)
        if not payload and size_bytes <= 0:
            continue
        processed += 1

        target = base_dir / f"{idx:03d}_{filename}"
        ref: dict[str, Any] = {
            "status": "pending",
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": payload_size_bytes,
        }

        if payload_size_bytes > MAX_FILE_SIZE:
            ref["status"] = "rejected"
            ref["reason"] = "file_too_large"
            rejected += 1
            attachment_id = store_message_attachment(
                db_path,
                tenant_id=tenant_id,
                message_id=message_id,
                filename=filename,
                mime_type=mime_type,
                size_bytes=payload_size_bytes,
                content_ref=ref,
            )
            attachment_ids.append(attachment_id)
            continue

        if tenant_usage_bytes + payload_size_bytes > MAIL_ATTACHMENT_TENANT_QUOTA_BYTES:
            ref["status"] = "rejected"
            ref["reason"] = "tenant_quota_exceeded"
            rejected += 1
            attachment_id = store_message_attachment(
                db_path,
                tenant_id=tenant_id,
                message_id=message_id,
                filename=filename,
                mime_type=mime_type,
                size_bytes=payload_size_bytes,
                content_ref=ref,
            )
            attachment_ids.append(attachment_id)
            continue

        try:
            target.write_bytes(payload)
            tenant_usage_bytes += payload_size_bytes
            from app.core.malware_scanner import scan_file_stream
            from app.core.upload_pipeline import process_upload

            if not scan_file_stream(target):
                quarantine_target = (
                    quarantine_dir
                    / f"{str(message_id)}_{idx:03d}_{uuid.uuid4().hex[:8]}_{filename}"
                )
                try:
                    target.replace(quarantine_target)
                    ref["storage_path"] = str(quarantine_target)
                except Exception:
                    ref["storage_path"] = str(target)
                ref["status"] = "quarantined"
                ref["reason"] = "malware_detected"
                quarantined += 1
                rejected += 1
            else:
                is_safe, info = process_upload(target, str(tenant_id or "default"))
                if is_safe:
                    ref["status"] = "accepted"
                    ref["sha256"] = str(info or "")
                    ref["storage_path"] = str(target)
                    accepted += 1
                else:
                    ref["status"] = "rejected"
                    ref["reason"] = str(info or "upload_pipeline_rejected")
                    ref["storage_path"] = str(target)
                    rejected += 1
        except Exception as exc:
            ref["status"] = "error"
            ref["reason"] = f"attachment_processing_failed:{exc.__class__.__name__}"
            ref["storage_path"] = str(target)
            errors += 1

        attachment_id = store_message_attachment(
            db_path,
            tenant_id=tenant_id,
            message_id=message_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=payload_size_bytes,
            content_ref=ref,
        )
        attachment_ids.append(attachment_id)

    return {
        "ok": True,
        "processed": processed,
        "accepted": accepted,
        "rejected": rejected,
        "quarantined": quarantined,
        "errors": errors,
        "attachment_ids": attachment_ids,
    }


def _find_customer_ids_by_emails(
    con: sqlite3.Connection,
    *,
    tenant_id: str,
    emails: list[str],
) -> set[str]:
    matched: set[str] = set()
    if not emails:
        return matched

    customer_cols = _table_columns(con, "customers")
    if _table_exists(con, "customers") and "id" in customer_cols and "tenant_id" in customer_cols:
        column_queries = {
            "email": """
                SELECT id
                FROM customers
                WHERE tenant_id=?
                  AND LOWER(TRIM(COALESCE(email, '')))=?
            """,
            "contact_email": """
                SELECT id
                FROM customers
                WHERE tenant_id=?
                  AND LOWER(TRIM(COALESCE(contact_email, '')))=?
            """,
            "email_address": """
                SELECT id
                FROM customers
                WHERE tenant_id=?
                  AND LOWER(TRIM(COALESCE(email_address, '')))=?
            """,
            "mail": """
                SELECT id
                FROM customers
                WHERE tenant_id=?
                  AND LOWER(TRIM(COALESCE(mail, '')))=?
            """,
        }
        for column_name in ("email", "contact_email", "email_address", "mail"):
            if column_name not in customer_cols:
                continue
            query = column_queries[column_name]
            for email in emails:
                rows = con.execute(query, (tenant_id, email)).fetchall()
                for row in rows:
                    value = str(row["id"] or "").strip()
                    if value:
                        matched.add(value)

    leads_cols = _table_columns(con, "leads")
    if _table_exists(con, "leads") and {
        "tenant_id",
        "contact_email",
        "customer_id",
    }.issubset(leads_cols):
        for email in emails:
            rows = con.execute(
                """
                SELECT DISTINCT customer_id
                FROM leads
                WHERE tenant_id=?
                  AND customer_id IS NOT NULL
                  AND TRIM(customer_id) != ''
                  AND LOWER(TRIM(COALESCE(contact_email, '')))=?
                """,
                (tenant_id, email),
            ).fetchall()
            for row in rows:
                value = str(row["customer_id"] or "").strip()
                if value:
                    matched.add(value)
    return matched


def link_thread_customers_by_email(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    emails: list[str],
) -> dict[str, Any]:
    ensure_postfach_schema(db_path)
    normalized = _normalize_email_candidates(emails)
    if not normalized:
        return {"ok": True, "linked": 0, "customer_ids": []}

    now = _now_iso()
    linked = 0
    customer_ids: list[str] = []
    con = _db(db_path)
    try:
        resolved_ids = sorted(
            _find_customer_ids_by_emails(con, tenant_id=tenant_id, emails=normalized)
        )
        for customer_id in resolved_ids:
            cur = con.execute(
                """
                INSERT OR IGNORE INTO mailbox_links(
                  id, tenant_id, thread_id, entity_type, entity_id, created_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (uuid.uuid4().hex, tenant_id, thread_id, "customer", customer_id, now),
            )
            if int(cur.rowcount or 0) > 0:
                linked += 1
        con.commit()
        customer_ids = resolved_ids
    finally:
        con.close()

    if linked > 0:
        _event(
            event_type="mailbox_thread_linked",
            entity_type="mailbox_thread",
            entity_text_id=thread_id,
            tenant_id=tenant_id,
            payload={
                "thread_id": thread_id,
                "links_created": int(linked),
                "entity_type": "customer",
            },
        )
    return {"ok": True, "linked": int(linked), "customer_ids": customer_ids}


def list_threads(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    filter_text: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_postfach_schema(db_path)
    lim = max(1, min(int(limit or 100), 500))
    ftxt = (filter_text or "").strip()
    con = _db(db_path)
    try:
        if ftxt:
            pattern = f"%{ftxt}%"
            rows = con.execute(
                """
                SELECT t.*
                FROM mailbox_threads t
                WHERE t.tenant_id=? AND t.account_id=?
                  AND (
                    t.subject_redacted LIKE ?
                    OR t.participants_redacted LIKE ?
                    OR EXISTS (
                      SELECT 1
                      FROM mailbox_messages m
                      WHERE m.tenant_id=t.tenant_id
                        AND m.thread_id=t.id
                        AND m.redacted_text LIKE ?
                    )
                  )
                ORDER BY t.last_message_at DESC, t.updated_at DESC
                LIMIT ?
                """,
                (tenant_id, account_id, pattern, pattern, pattern, lim),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT t.*
                FROM mailbox_threads t
                WHERE t.tenant_id=? AND t.account_id=?
                ORDER BY t.last_message_at DESC, t.updated_at DESC
                LIMIT ?
                """,
                (tenant_id, account_id, lim),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def search_messages(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str | None = None,
    query: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_postfach_schema(db_path)
    q = str(query or "").strip()
    if not q:
        return []
    pattern = f"%{q}%"
    lim = max(1, min(int(limit or 100), 500))
    con = _db(db_path)
    try:
        if account_id:
            rows = con.execute(
                """
                SELECT m.id, m.tenant_id, m.account_id, m.thread_id, m.direction, m.message_id_header,
                       m.from_redacted, m.to_redacted, m.subject_redacted, m.redacted_text,
                       m.has_attachments, m.received_at, m.created_at
                FROM mailbox_messages m
                WHERE m.tenant_id=? AND m.account_id=?
                  AND (
                    m.subject_redacted LIKE ?
                    OR m.from_redacted LIKE ?
                    OR m.to_redacted LIKE ?
                    OR m.redacted_text LIKE ?
                  )
                ORDER BY COALESCE(m.received_at, m.created_at) DESC, m.id DESC
                LIMIT ?
                """,
                (tenant_id, account_id, pattern, pattern, pattern, pattern, lim),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT m.id, m.tenant_id, m.account_id, m.thread_id, m.direction, m.message_id_header,
                       m.from_redacted, m.to_redacted, m.subject_redacted, m.redacted_text,
                       m.has_attachments, m.received_at, m.created_at
                FROM mailbox_messages m
                WHERE m.tenant_id=?
                  AND (
                    m.subject_redacted LIKE ?
                    OR m.from_redacted LIKE ?
                    OR m.to_redacted LIKE ?
                    OR m.redacted_text LIKE ?
                  )
                ORDER BY COALESCE(m.received_at, m.created_at) DESC, m.id DESC
                LIMIT ?
                """,
                (tenant_id, pattern, pattern, pattern, pattern, lim),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_thread(
    db_path: Path, *, tenant_id: str, thread_id: str
) -> dict[str, Any] | None:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        thread_row = con.execute(
            """
            SELECT *
            FROM mailbox_threads
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant_id, thread_id),
        ).fetchone()
        if not thread_row:
            return None

        message_rows = con.execute(
            """
            SELECT id, direction, message_id_header, in_reply_to, references_header,
                   from_redacted, to_redacted, subject_redacted, redacted_text,
                   has_attachments, received_at, created_at
            FROM mailbox_messages
            WHERE tenant_id=? AND thread_id=?
            ORDER BY created_at ASC, id ASC
            """,
            (tenant_id, thread_id),
        ).fetchall()
        messages = [dict(r) for r in message_rows]
        attachments_by_message: dict[str, list[dict[str, Any]]] = {}
        if messages:
            rows = con.execute(
                """
                SELECT a.id, a.message_id, a.filename_redacted, a.mime_type, a.size_bytes, a.content_ref, a.created_at
                FROM mailbox_attachments a
                JOIN mailbox_messages m
                  ON m.id = a.message_id
                 AND m.tenant_id = a.tenant_id
                WHERE a.tenant_id=? AND m.thread_id=?
                ORDER BY a.created_at ASC, a.id ASC
                """,
                (tenant_id, thread_id),
            ).fetchall()
            for row in rows:
                item = dict(row)
                raw_ref = str(item.get("content_ref") or "").strip()
                if raw_ref:
                    try:
                        item["content_ref_json"] = json.loads(raw_ref)
                    except Exception:
                        item["content_ref_json"] = None
                else:
                    item["content_ref_json"] = None
                mid = str(item.get("message_id") or "")
                attachments_by_message.setdefault(mid, []).append(item)
            for msg in messages:
                msg["attachments"] = attachments_by_message.get(str(msg.get("id")), [])

        links = con.execute(
            """
            SELECT id, entity_type, entity_id, created_at
            FROM mailbox_links
            WHERE tenant_id=? AND thread_id=?
            ORDER BY created_at DESC
            """,
            (tenant_id, thread_id),
        ).fetchall()

        return {
            "thread": dict(thread_row),
            "messages": messages,
            "links": [dict(r) for r in links],
        }
    finally:
        con.close()


def create_draft(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    thread_id: str | None,
    to_value: str,
    subject_value: str,
    body_value: str,
) -> str:
    ensure_postfach_schema(db_path)
    now = _now_iso()
    draft_id = uuid.uuid4().hex

    to_clean = str(to_value or "").strip()
    subject_clean = str(subject_value or "").strip()
    body_clean = str(body_value or "").strip()

    to_enc = encrypt_text(to_clean)
    subject_enc = encrypt_text(subject_clean)
    body_enc = encrypt_text(body_clean)

    con = _db(db_path)
    try:
        con.execute(
            """
            INSERT INTO mailbox_drafts(
              id, tenant_id, account_id, thread_id,
              to_redacted, subject_redacted, body_redacted,
              to_encrypted, subject_encrypted, body_encrypted,
              status, created_at, updated_at, sent_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                draft_id,
                tenant_id,
                account_id,
                thread_id,
                knowledge_redact_text(to_clean, max_len=220),
                knowledge_redact_text(subject_clean, max_len=260),
                knowledge_redact_text(body_clean, max_len=12000),
                to_enc,
                subject_enc,
                body_enc,
                "draft",
                now,
                now,
                None,
            ),
        )
        con.commit()
    finally:
        con.close()

    _event(
        event_type="mailbox_draft_created",
        entity_type="mailbox_draft",
        entity_text_id=draft_id,
        tenant_id=tenant_id,
        payload={
            "account_id": account_id,
            "thread_id": thread_id,
            "draft_id": draft_id,
        },
    )
    return draft_id


def get_draft(
    db_path: Path,
    *,
    tenant_id: str,
    draft_id: str,
    include_plain: bool = False,
) -> dict[str, Any] | None:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        row = con.execute(
            """
            SELECT *
            FROM mailbox_drafts
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant_id, draft_id),
        ).fetchone()
        if not row:
            return None
        out = dict(row)
    finally:
        con.close()

    if include_plain:
        out["to_plain"] = decrypt_text(str(out.get("to_encrypted") or ""))
        out["subject_plain"] = decrypt_text(str(out.get("subject_encrypted") or ""))
        out["body_plain"] = decrypt_text(str(out.get("body_encrypted") or ""))
    return out


def mark_draft_sent(db_path: Path, *, tenant_id: str, draft_id: str) -> None:
    ensure_postfach_schema(db_path)
    now = _now_iso()
    con = _db(db_path)
    try:
        con.execute(
            """
            UPDATE mailbox_drafts
            SET status='sent', sent_at=?, updated_at=?
            WHERE tenant_id=? AND id=?
            """,
            (now, now, tenant_id, draft_id),
        )
        con.commit()
    finally:
        con.close()

    _event(
        event_type="mailbox_draft_sent",
        entity_type="mailbox_draft",
        entity_text_id=draft_id,
        tenant_id=tenant_id,
        payload={"draft_id": draft_id},
    )


def list_drafts_for_thread(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    ensure_postfach_schema(db_path)
    lim = max(1, min(int(limit or 20), 200))
    con = _db(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, tenant_id, account_id, thread_id, to_redacted, subject_redacted,
                   body_redacted, status, created_at, updated_at, sent_at
            FROM mailbox_drafts
            WHERE tenant_id=? AND thread_id=?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (tenant_id, thread_id, lim),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _first_email_from_header(value: str) -> str:
    parsed = getaddresses([str(value or "")])
    for _name, addr in parsed:
        lowered = str(addr or "").strip().lower()
        if lowered and "@" in lowered:
            return lowered
    return ""


def _parse_reply_target_from_raw(raw_eml_blob: str) -> tuple[str, str]:
    blob = str(raw_eml_blob or "").strip()
    if not blob:
        return "", ""
    try:
        msg = BytesParser(policy=policy.default).parsebytes(decrypt_bytes(blob))
    except Exception:
        return "", ""

    reply_to = _first_email_from_header(str(msg.get("reply-to") or ""))
    sender = _first_email_from_header(str(msg.get("from") or ""))
    recipient = _first_email_from_header(str(msg.get("to") or ""))
    subject = str(msg.get("subject") or "").strip()
    target = reply_to or sender or recipient
    return target, subject


def generate_local_reply_draft(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    account_id: str | None = None,
    instruction: str = "",
) -> dict[str, Any]:
    ensure_postfach_schema(db_path)
    con = _db(db_path)
    try:
        thread = con.execute(
            """
            SELECT id, account_id, subject_redacted
            FROM mailbox_threads
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant_id, thread_id),
        ).fetchone()
        if not thread:
            return {"ok": False, "reason": "thread_not_found"}

        resolved_account = str(account_id or thread["account_id"] or "").strip()
        if not resolved_account:
            return {"ok": False, "reason": "account_not_found"}

        msg_row = con.execute(
            """
            SELECT raw_eml_blob, subject_redacted, redacted_text
            FROM mailbox_messages
            WHERE tenant_id=? AND thread_id=?
            ORDER BY CASE WHEN direction='inbound' THEN 0 ELSE 1 END, created_at DESC, id DESC
            LIMIT 1
            """,
            (tenant_id, thread_id),
        ).fetchone()
        if not msg_row:
            return {"ok": False, "reason": "thread_empty"}
    finally:
        con.close()

    reply_to, subject_plain = _parse_reply_target_from_raw(
        str(msg_row["raw_eml_blob"] or "")
    )
    if not reply_to:
        return {"ok": False, "reason": "recipient_unavailable"}

    subject_seed = str(subject_plain or msg_row["subject_redacted"] or "").strip()
    if not subject_seed:
        subject_seed = str(thread["subject_redacted"] or "").strip() or "Antwort"
    lower_subject = subject_seed.lower()
    if not lower_subject.startswith("re:"):
        subject_seed = f"Re: {subject_seed}"

    snippet = str(msg_row["redacted_text"] or "").strip()
    if len(snippet) > 320:
        snippet = snippet[:320].rstrip() + "..."

    body_parts = [
        "Hallo,",
        "",
        "danke fuer Ihre Nachricht.",
    ]
    if snippet:
        body_parts.extend(["", f"Bezug: {snippet}"])
    if instruction.strip():
        body_parts.extend(["", f"Bearbeitungshinweis: {instruction.strip()}"])
    body_parts.extend(
        [
            "",
            "Ich melde mich mit der finalen Rueckmeldung schnellstmoeglich.",
            "",
            "Viele Gruesse",
        ]
    )
    body_text = "\n".join(body_parts).strip()

    draft_id = create_draft(
        db_path,
        tenant_id=tenant_id,
        account_id=resolved_account,
        thread_id=thread_id,
        to_value=reply_to,
        subject_value=subject_seed,
        body_value=body_text,
    )
    return {
        "ok": True,
        "reason": "ok",
        "draft_id": draft_id,
        "thread_id": thread_id,
        "account_id": resolved_account,
        "recipient": reply_to,
    }


def generate_local_ai_reply_draft(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    account_id: str | None = None,
    instruction: str = "",
) -> dict[str, Any]:
    base = generate_local_reply_draft(
        db_path,
        tenant_id=tenant_id,
        thread_id=thread_id,
        account_id=account_id,
        instruction=instruction,
    )
    if not bool(base.get("ok")):
        return base

    draft_id = str(base.get("draft_id") or "")
    if not draft_id:
        return {"ok": False, "reason": "draft_creation_failed"}

    draft = get_draft(db_path, tenant_id=tenant_id, draft_id=draft_id, include_plain=True)
    if not draft:
        return {"ok": False, "reason": "draft_not_found"}

    thread = get_thread(db_path, tenant_id=tenant_id, thread_id=thread_id) or {}
    messages = thread.get("messages", [])
    facts = {
        "thread_id": thread_id,
        "message_count": str(len(messages)),
        "instruction": instruction.strip(),
    }

    try:
        from app.plugins.mail import MailAgent, MailInput, MailOptions

        agent = MailAgent()
        result = agent.generate(
            MailInput(
                context="Antwort auf eingegangene E-Mail im lokalen Postfach",
                facts=facts,
                attachments=[],
                draft=str(draft.get("body_plain") or ""),
                recipient_name="",
                recipient_company="",
            ),
            MailOptions(
                tone="neutral",
                length="normal",
                legal_level="light",
                goal="nachbesserung",
                recipient_type="kunde",
                rewrite_mode="local",
            ),
        )
        suggested_subject = str(result.get("subject") or "").strip() or str(draft.get("subject_plain") or "")
        suggested_body = str(result.get("body") or "").strip() or str(draft.get("body_plain") or "")
    except Exception:
        return {"ok": True, "reason": "fallback_local_template", "draft_id": draft_id}

    final_draft_id = create_draft(
        db_path,
        tenant_id=tenant_id,
        account_id=str(draft.get("account_id") or ""),
        thread_id=thread_id,
        to_value=str(draft.get("to_plain") or ""),
        subject_value=suggested_subject,
        body_value=suggested_body,
    )
    return {
        "ok": True,
        "reason": "ok",
        "draft_id": final_draft_id,
        "source_draft_id": draft_id,
        "thread_id": thread_id,
    }


def create_calendar_followup_from_thread(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    owner: str,
    created_by: str,
) -> dict[str, Any]:
    data = get_thread(db_path, tenant_id=tenant_id, thread_id=thread_id)
    if not data:
        return {"ok": False, "reason": "thread_not_found"}

    messages = data.get("messages", [])
    merged = "\n".join(str(m.get("redacted_text") or "") for m in messages)
    date_matches = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", merged)
    time_matches = re.findall(r"\b\d{1,2}:\d{2}\b", merged)
    due_hint = date_matches[0] if date_matches else ""
    time_hint = time_matches[0] if time_matches else ""
    subject = str((data.get("thread") or {}).get("subject_redacted") or "Mail Termin")

    task_id = int(
        core.task_create(
            tenant=tenant_id,
            severity="INFO",
            task_type="CALENDAR_EVENT",
            title=f"Termin aus Mail: {subject[:80]}",
            details=(
                f"Thread: {thread_id}\n"
                f"Owner: {(owner or '').strip() or 'unassigned'}\n"
                f"DateHint: {due_hint}\n"
                f"TimeHint: {time_hint}"
            ),
            token=f"postfach:calendar:{thread_id}",
            meta={
                "source": "postfach",
                "thread_id": thread_id,
                "owner": (owner or "").strip(),
                "date_hint": due_hint,
                "time_hint": time_hint,
            },
            created_by=created_by,
        )
    )

    _event(
        event_type="mailbox_calendar_followup_created",
        entity_type="mailbox_thread",
        entity_text_id=thread_id,
        tenant_id=tenant_id,
        payload={"thread_id": thread_id, "task_id": task_id},
    )
    return {
        "ok": True,
        "reason": "ok",
        "task_id": task_id,
        "date_hint": due_hint,
        "time_hint": time_hint,
    }


def export_thread_pdf_and_archive(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
) -> dict[str, Any]:
    data = get_thread(db_path, tenant_id=tenant_id, thread_id=thread_id)
    if not data:
        return {"ok": False, "reason": "thread_not_found"}

    thread = data.get("thread") or {}
    messages = data.get("messages") or []
    subject = str(thread.get("subject_redacted") or "mail_thread")
    safe_subject = re.sub(r"[^A-Za-z0-9._-]+", "_", subject).strip("._")[:80] or "mail_thread"
    export_dir = Config.USER_DATA_ROOT / "mail_exports" / str(tenant_id or "default")
    export_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = export_dir / f"{safe_subject}_{str(thread_id)[:8]}.pdf"

    body_lines: list[str] = [f"Thread: {thread_id}", f"Subject: {subject}", ""]
    for m in messages:
        body_lines.extend(
            [
                f"From: {m.get('from_redacted') or ''}",
                f"To: {m.get('to_redacted') or ''}",
                f"Received: {m.get('received_at') or m.get('created_at') or ''}",
                f"Message: {m.get('redacted_text') or ''}",
                "",
            ]
        )
    body_text = "\n".join(body_lines).strip()

    try:
        import fitz  # type: ignore

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        rect = fitz.Rect(36, 36, 559, 806)
        page.insert_textbox(rect, body_text, fontsize=10, fontname="helv")
        doc.save(str(pdf_path))
        doc.close()
    except Exception:
        return {"ok": False, "reason": "pdf_backend_unavailable"}

    try:
        from app.core.malware_scanner import scan_file_stream
        from app.core.upload_pipeline import process_upload
    except Exception:
        return {"ok": False, "reason": "upload_pipeline_unavailable"}

    if not scan_file_stream(pdf_path):
        return {"ok": False, "reason": "malware_detected"}
    ok, info = process_upload(pdf_path, str(tenant_id or "default"))
    if not ok:
        return {"ok": False, "reason": str(info or "upload_pipeline_rejected")}

    _event(
        event_type="mailbox_thread_pdf_exported",
        entity_type="mailbox_thread",
        entity_text_id=thread_id,
        tenant_id=tenant_id,
        payload={
            "thread_id": thread_id,
            "pdf_path": str(pdf_path),
            "file_hash": str(info or ""),
        },
    )
    return {
        "ok": True,
        "reason": "ok",
        "pdf_path": str(pdf_path),
        "file_hash": str(info or ""),
    }


def link_entities(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    customer_id: str | None = None,
    project_id: str | None = None,
    lead_id: str | None = None,
) -> dict[str, Any]:
    ensure_postfach_schema(db_path)
    candidates = {
        "customer": str(customer_id or "").strip(),
        "project": str(project_id or "").strip(),
        "lead": str(lead_id or "").strip(),
    }
    now = _now_iso()
    created = 0
    con = _db(db_path)
    try:
        for entity_type, entity_id in candidates.items():
            if not entity_id:
                continue
            link_id = uuid.uuid4().hex
            cur = con.execute(
                """
                INSERT OR IGNORE INTO mailbox_links(
                  id, tenant_id, thread_id, entity_type, entity_id, created_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (link_id, tenant_id, thread_id, entity_type, entity_id, now),
            )
            if int(cur.rowcount or 0) > 0:
                created += 1
        con.commit()
    finally:
        con.close()

    if created:
        _event(
            event_type="mailbox_thread_linked",
            entity_type="mailbox_thread",
            entity_text_id=thread_id,
            tenant_id=tenant_id,
            payload={
                "thread_id": thread_id,
                "links_created": int(created),
            },
        )

    return {"ok": True, "links_created": int(created)}


def extract_structured(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    schema_name: str,
) -> dict[str, Any]:
    data = get_thread(db_path, tenant_id=tenant_id, thread_id=thread_id)
    if not data:
        return {"ok": False, "reason": "thread_not_found", "fields": {}}

    messages = data.get("messages", [])
    merged = "\n".join(str(m.get("redacted_text") or "") for m in messages)
    schema = str(schema_name or "default").strip().lower()

    email_matches = re.findall(r"\[redacted-email\]", merged)
    phone_matches = re.findall(r"\[redacted-phone\]", merged)
    date_matches = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", merged)

    fields = {
        "schema": schema,
        "contains_redacted_email": bool(email_matches),
        "contains_redacted_phone": bool(phone_matches),
        "date_candidates": date_matches[:5],
        "line_count": len([ln for ln in merged.splitlines() if ln.strip()]),
    }

    _event(
        event_type="mailbox_thread_extracted",
        entity_type="mailbox_thread",
        entity_text_id=thread_id,
        tenant_id=tenant_id,
        payload={
            "thread_id": thread_id,
            "schema": schema,
            "line_count": int(fields["line_count"]),
        },
    )

    return {"ok": True, "reason": "ok", "fields": fields}


def extract_intake(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    schema_name: str = "intake_v1",
) -> dict[str, Any]:
    data = get_thread(db_path, tenant_id=tenant_id, thread_id=thread_id)
    if not data:
        return {"ok": False, "reason": "thread_not_found", "fields": {}}
    messages = data.get("messages", [])
    merged = "\n".join(str(m.get("redacted_text") or "") for m in messages)
    subject = str((data.get("thread") or {}).get("subject_redacted") or "")
    lowered = merged.lower()

    intent = "general_inquiry"
    if any(k in lowered for k in ["angebot", "anfrage", "preis"]):
        intent = "quote_request"
    elif any(k in lowered for k in ["reklamation", "defekt", "mangel"]):
        intent = "complaint"
    elif any(k in lowered for k in ["termin", "besichtigung", "vor ort"]):
        intent = "appointment_request"

    phone_candidates = re.findall(r"\+?\d[\d\s/().-]{6,}", merged)
    date_candidates = re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", merged)
    domain_candidates = re.findall(r"\b[a-z0-9.-]+\.[a-z]{2,}\b", lowered)

    fields = {
        "schema": str(schema_name or "intake_v1").strip().lower(),
        "thread_id": thread_id,
        "subject": subject,
        "intent": intent,
        "date_candidates": date_candidates[:8],
        "phone_candidates": phone_candidates[:8],
        "domain_candidates": domain_candidates[:8],
        "message_count": len(messages),
    }

    ensure_postfach_schema(db_path)
    now = _now_iso()
    artifact_id = uuid.uuid4().hex
    con = _db(db_path)
    try:
        con.execute(
            """
            INSERT INTO mailbox_intake_artifacts(
              id, tenant_id, thread_id, schema_name, fields_json, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id, thread_id, schema_name) DO UPDATE SET
              fields_json=excluded.fields_json,
              updated_at=excluded.updated_at
            """,
            (
                artifact_id,
                tenant_id,
                thread_id,
                fields["schema"],
                json.dumps(fields, ensure_ascii=False),
                now,
                now,
            ),
        )
        con.commit()
    finally:
        con.close()

    _event(
        event_type="mailbox_thread_intake_extracted",
        entity_type="mailbox_thread",
        entity_text_id=thread_id,
        tenant_id=tenant_id,
        payload={
            "thread_id": thread_id,
            "schema": fields["schema"],
            "intent": intent,
            "message_count": int(fields["message_count"]),
        },
    )
    return {"ok": True, "reason": "ok", "fields": fields}


def safety_check_draft(
    db_path: Path,
    *,
    tenant_id: str,
    draft_id: str,
) -> dict[str, Any]:
    draft = get_draft(
        db_path, tenant_id=tenant_id, draft_id=draft_id, include_plain=True
    )
    if not draft:
        return {"ok": False, "reason": "draft_not_found", "warnings": []}
    account = get_account(
        db_path, tenant_id=tenant_id, account_id=str(draft.get("account_id") or "")
    )
    if not account:
        return {"ok": False, "reason": "account_not_found", "warnings": []}

    warnings: list[dict[str, str]] = []
    to_plain = str(draft.get("to_plain") or "").strip().lower()
    body_plain = str(draft.get("body_plain") or "").strip()
    account_user = str(
        account.get("smtp_username") or account.get("imap_username") or ""
    ).lower()
    account_domain = account_user.split("@", 1)[1] if "@" in account_user else ""
    recipient_domain = to_plain.split("@", 1)[1] if "@" in to_plain else ""

    if recipient_domain and account_domain and recipient_domain != account_domain:
        warnings.append(
            {
                "code": "recipient_domain_mismatch",
                "message": "Empfaenger-Domain weicht von Konto-Domain ab.",
            }
        )

    for url in re.findall(r"https?://[^\s)]+", body_plain, flags=re.IGNORECASE):
        host = (
            re.sub(r"^https?://", "", url, flags=re.IGNORECASE).split("/", 1)[0].lower()
        )
        if "xn--" in host:
            warnings.append(
                {
                    "code": "punycode_link",
                    "message": "Punycode-Link erkannt, bitte URL pruefen.",
                }
            )
        if host in {"bit.ly", "t.co", "tinyurl.com", "goo.gl"}:
            warnings.append(
                {
                    "code": "shortener_link",
                    "message": "URL-Shortener erkannt, Zieladresse pruefen.",
                }
            )

    if re.search(r"\b[a-z]{2}\d{2}[a-z0-9]{10,30}\b", body_plain, flags=re.IGNORECASE):
        warnings.append(
            {
                "code": "possible_iban",
                "message": "Moegliche IBAN im Entwurf erkannt.",
            }
        )

    if re.search(r"\+?\d[\d\s/().-]{8,}", body_plain):
        warnings.append(
            {
                "code": "possible_phone",
                "message": "Telefonnummer im Entwurf erkannt.",
            }
        )

    return {
        "ok": True,
        "reason": "ok",
        "warning_count": len(warnings),
        "warnings": warnings[:10],
    }


def create_followup_task(
    db_path: Path,
    *,
    tenant_id: str,
    thread_id: str,
    due_at: str,
    owner: str,
    title: str,
    created_by: str,
) -> dict[str, Any]:
    ensure_postfach_schema(db_path)
    clean_title = (title or "").strip() or "Postfach Follow-up"
    clean_owner = (owner or "").strip() or "unassigned"
    clean_due = (due_at or "").strip()
    task_id = int(
        core.task_create(
            tenant=tenant_id,
            severity="INFO",
            task_type="FOLLOWUP",
            title=clean_title,
            details=f"Thread: {thread_id}\nOwner: {clean_owner}\nDue: {clean_due}",
            token=f"postfach:{thread_id}",
            meta={
                "source": "postfach",
                "thread_id": thread_id,
                "owner": clean_owner,
                "due_at": clean_due,
            },
            created_by=created_by,
        )
    )

    _event(
        event_type="mailbox_followup_created",
        entity_type="mailbox_thread",
        entity_text_id=thread_id,
        tenant_id=tenant_id,
        payload={
            "thread_id": thread_id,
            "task_id": int(task_id),
            "owner": clean_owner,
        },
    )
    return {"ok": True, "task_id": int(task_id)}
