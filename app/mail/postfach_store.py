from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import kukanilea_core_v3_fixed as core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append
from app.knowledge import knowledge_redact_text

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as exc:  # pragma: no cover
    raise RuntimeError("cryptography_required_for_postfach") from exc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(r["name"]) for r in rows}


def _ensure_column(con: sqlite3.Connection, table: str, column_def: str) -> None:
    col_name = str(column_def.split()[0]).strip()
    if col_name in _table_columns(con, table):
        return
    con.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


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
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return True
    return datetime.now(timezone.utc).timestamp() >= (dt.timestamp() - skew_seconds)


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
        (f"{message_id_clean or ''}|{subject_redacted}|{body_redacted}").encode("utf-8")
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

        messages = con.execute(
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
            "messages": [dict(r) for r in messages],
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
