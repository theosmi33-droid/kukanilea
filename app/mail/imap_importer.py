from __future__ import annotations

import base64
import hashlib
import imaplib
import json
import os
import sqlite3
import ssl
from datetime import datetime
from email import message_from_bytes, policy
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import Config
from app.knowledge import knowledge_redact_text


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def ensure_mail_schema(db_path: Path) -> None:
    con = _db(db_path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mail_accounts(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              label TEXT NOT NULL,
              imap_host TEXT NOT NULL,
              imap_port INTEGER NOT NULL,
              imap_username TEXT NOT NULL,
              auth_mode TEXT NOT NULL DEFAULT 'password',
              imap_password_ref TEXT,
              xoauth2_token_ref TEXT,
              sync_enabled INTEGER NOT NULL DEFAULT 1,
              last_sync_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mail_messages(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              account_id TEXT NOT NULL,
              uid TEXT NOT NULL,
              message_id TEXT,
              from_redacted TEXT NOT NULL,
              to_redacted TEXT NOT NULL,
              subject_redacted TEXT NOT NULL,
              received_at TEXT NOT NULL,
              body_text_redacted TEXT NOT NULL,
              has_attachments INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              UNIQUE(account_id, uid)
            );
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_mail_accounts_tenant ON mail_accounts(tenant_id)"
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_mail_messages_lookup
            ON mail_messages(tenant_id, account_id, received_at DESC)
            """
        )
        con.commit()
    finally:
        con.close()


def _secrets_path() -> Path:
    path = Config.USER_DATA_ROOT / "secrets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_secrets() -> dict[str, str]:
    path = _secrets_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _save_secrets(data: dict[str, str]) -> None:
    path = _secrets_path()
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o600)


def _encryption_key() -> bytes:
    raw = str(os.environ.get("EMAIL_ENCRYPTION_KEY", "") or "").strip()
    if not raw:
        raise ValueError("email_encryption_key_missing")
    if raw.startswith("base64:"):
        decoded = base64.urlsafe_b64decode(raw.split(":", 1)[1].encode("utf-8"))
        if len(decoded) in {16, 24, 32}:
            return decoded
    try:
        as_hex = bytes.fromhex(raw)
        if len(as_hex) in {16, 24, 32}:
            return as_hex
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _encrypt_secret(secret: str) -> str:
    key = _encryption_key()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, secret.encode("utf-8"), b"kukanilea-email-secret")
    packed = nonce + ciphertext
    return "aesgcm:" + base64.urlsafe_b64encode(packed).decode("ascii")


def _decrypt_secret(payload: str) -> str:
    raw = str(payload or "")
    if raw.startswith("aesgcm:"):
        encoded = raw.split(":", 1)[1]
        packed = base64.urlsafe_b64decode(encoded.encode("ascii"))
        nonce, ciphertext = packed[:12], packed[12:]
        aes = AESGCM(_encryption_key())
        return aes.decrypt(nonce, ciphertext, b"kukanilea-email-secret").decode("utf-8")
    # Legacy fallback (pre-encryption local format).
    # Keep fail-closed semantics: even legacy payloads require EMAIL_ENCRYPTION_KEY.
    _encryption_key()
    return base64.b64decode(raw.encode("ascii")).decode("utf-8")


def store_secret(secret: str) -> str:
    ref = (
        f"sec_{hashlib.sha256((secret + _now_iso()).encode('utf-8')).hexdigest()[:24]}"
    )
    data = _load_secrets()
    data[ref] = _encrypt_secret(secret)
    _save_secrets(data)
    return ref


def load_secret(ref: str) -> str:
    data = _load_secrets()
    value = data.get(ref or "", "")
    if not value:
        return ""
    try:
        secret = _decrypt_secret(value)
        # Auto-migrate legacy payloads after successful read.
        if not str(value).startswith("aesgcm:"):
            data[str(ref)] = _encrypt_secret(secret)
            _save_secrets(data)
        return secret
    except Exception:
        return ""


def save_account(
    db_path: Path,
    *,
    tenant_id: str,
    label: str,
    imap_host: str,
    imap_port: int,
    imap_username: str,
    auth_mode: str = "password",
    imap_password_ref: str | None = None,
    xoauth2_token_ref: str | None = None,
) -> str:
    ensure_mail_schema(db_path)
    now = _now_iso()
    account_id = hashlib.sha256(
        f"{tenant_id}|{imap_host}|{imap_username}".encode("utf-8")
    ).hexdigest()[:24]
    con = _db(db_path)
    try:
        con.execute(
            """
            INSERT INTO mail_accounts(
              id, tenant_id, label, imap_host, imap_port, imap_username,
              auth_mode, imap_password_ref, xoauth2_token_ref, created_at, updated_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              label=excluded.label,
              imap_host=excluded.imap_host,
              imap_port=excluded.imap_port,
              imap_username=excluded.imap_username,
              auth_mode=excluded.auth_mode,
              imap_password_ref=COALESCE(excluded.imap_password_ref, mail_accounts.imap_password_ref),
              xoauth2_token_ref=COALESCE(excluded.xoauth2_token_ref, mail_accounts.xoauth2_token_ref),
              updated_at=excluded.updated_at
            """,
            (
                account_id,
                tenant_id,
                label,
                imap_host,
                int(imap_port),
                imap_username,
                auth_mode,
                imap_password_ref,
                xoauth2_token_ref,
                now,
                now,
            ),
        )
        con.commit()
        return account_id
    finally:
        con.close()


def list_accounts(db_path: Path, tenant_id: str) -> list[dict[str, Any]]:
    ensure_mail_schema(db_path)
    con = _db(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, tenant_id, label, imap_host, imap_port, imap_username, auth_mode,
                   sync_enabled, last_sync_at, created_at, updated_at
            FROM mail_accounts
            WHERE tenant_id=?
            ORDER BY updated_at DESC
            """,
            (tenant_id,),
        ).fetchall()
        out = [dict(r) for r in rows]
        for row in out:
            row["imap_username_redacted"] = knowledge_redact_text(
                str(row.get("imap_username") or ""), max_len=80
            )
            row.pop("imap_username", None)
        return out
    finally:
        con.close()


def get_account(
    db_path: Path, tenant_id: str, account_id: str
) -> dict[str, Any] | None:
    ensure_mail_schema(db_path)
    con = _db(db_path)
    try:
        row = con.execute(
            """
            SELECT *
            FROM mail_accounts
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant_id, account_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def _extract_body_text(msg) -> tuple[str, bool]:
    has_attachments = False
    text_plain: list[str] = []
    text_html: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = str(part.get_content_type() or "").lower()
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                has_attachments = True
                continue
            try:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = ""
            if ctype == "text/plain":
                text_plain.append(decoded)
            elif ctype == "text/html":
                text_html.append(decoded)
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
        except Exception:
            decoded = ""
        ctype = str(msg.get_content_type() or "").lower()
        if ctype == "text/html":
            text_html.append(decoded)
        else:
            text_plain.append(decoded)
    body = "\n".join(text_plain).strip() or "\n".join(text_html).strip()
    return body, has_attachments


def sync_account(
    db_path: Path,
    *,
    tenant_id: str,
    account_id: str,
    password: str,
    limit: int = 50,
) -> dict[str, Any]:
    ensure_mail_schema(db_path)
    account = get_account(db_path, tenant_id, account_id)
    if not account:
        return {"ok": False, "reason": "account_not_found", "imported": 0}
    if not password:
        return {"ok": False, "reason": "password_missing", "imported": 0}

    host = str(account.get("imap_host") or "")
    username = str(account.get("imap_username") or "")
    port = int(account.get("imap_port") or 993)
    lim = max(1, min(int(limit or 50), 200))

    imported = 0
    try:
        context = ssl.create_default_context()
        with imaplib.IMAP4_SSL(host, port, ssl_context=context) as imap:
            imap.login(username, password)
            imap.select("INBOX")
            status, data = imap.uid("search", None, "ALL")
            if status != "OK":
                return {"ok": False, "reason": "imap_search_failed", "imported": 0}
            raw_uids = data[0].decode("utf-8", errors="ignore").split() if data else []
            uids = raw_uids[-lim:]
            con = _db(db_path)
            try:
                for uid in uids:
                    f_status, msg_data = imap.uid("fetch", uid, "(RFC822)")
                    if f_status != "OK" or not msg_data:
                        continue
                    raw_bytes = b""
                    for part in msg_data:
                        if (
                            isinstance(part, tuple)
                            and len(part) >= 2
                            and isinstance(part[1], (bytes, bytearray))
                        ):
                            raw_bytes = bytes(part[1])
                            break
                    if not raw_bytes:
                        continue
                    msg = message_from_bytes(raw_bytes, policy=policy.default)
                    body_raw, has_attachments = _extract_body_text(msg)
                    from_redacted = knowledge_redact_text(
                        str(msg.get("from") or ""), max_len=180
                    )
                    to_redacted = knowledge_redact_text(
                        str(msg.get("to") or ""), max_len=180
                    )
                    subject_redacted = knowledge_redact_text(
                        str(msg.get("subject") or ""), max_len=240
                    )
                    body_redacted = knowledge_redact_text(body_raw, max_len=12000)
                    received_at = _now_iso()
                    message_id = str(msg.get("message-id") or "")
                    row_id = hashlib.sha256(
                        f"{tenant_id}|{account_id}|{uid}".encode("utf-8")
                    ).hexdigest()[:24]
                    con.execute(
                        """
                        INSERT INTO mail_messages(
                          id, tenant_id, account_id, uid, message_id,
                          from_redacted, to_redacted, subject_redacted,
                          received_at, body_text_redacted, has_attachments, created_at
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(account_id, uid) DO UPDATE SET
                          message_id=excluded.message_id,
                          from_redacted=excluded.from_redacted,
                          to_redacted=excluded.to_redacted,
                          subject_redacted=excluded.subject_redacted,
                          received_at=excluded.received_at,
                          body_text_redacted=excluded.body_text_redacted,
                          has_attachments=excluded.has_attachments
                        """,
                        (
                            row_id,
                            tenant_id,
                            account_id,
                            uid,
                            message_id,
                            from_redacted,
                            to_redacted,
                            subject_redacted,
                            received_at,
                            body_redacted,
                            1 if has_attachments else 0,
                            _now_iso(),
                        ),
                    )
                    imported += 1
                con.execute(
                    "UPDATE mail_accounts SET last_sync_at=?, updated_at=? WHERE tenant_id=? AND id=?",
                    (_now_iso(), _now_iso(), tenant_id, account_id),
                )
                con.commit()
            finally:
                con.close()
    except Exception as exc:
        return {
            "ok": False,
            "reason": "imap_sync_failed",
            "error": knowledge_redact_text(str(exc), max_len=180),
            "imported": imported,
        }
    return {"ok": True, "reason": "ok", "imported": imported}


def list_messages(
    db_path: Path, tenant_id: str, *, account_id: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    ensure_mail_schema(db_path)
    lim = max(1, min(int(limit or 100), 500))
    con = _db(db_path)
    try:
        if account_id:
            rows = con.execute(
                """
                SELECT id, account_id, uid, from_redacted, to_redacted,
                       subject_redacted, received_at, has_attachments
                FROM mail_messages
                WHERE tenant_id=? AND account_id=?
                ORDER BY received_at DESC, created_at DESC
                LIMIT ?
                """,
                (tenant_id, account_id, lim),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT id, account_id, uid, from_redacted, to_redacted,
                       subject_redacted, received_at, has_attachments
                FROM mail_messages
                WHERE tenant_id=?
                ORDER BY received_at DESC, created_at DESC
                LIMIT ?
                """,
                (tenant_id, lim),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_message(
    db_path: Path, tenant_id: str, message_id: str
) -> dict[str, Any] | None:
    ensure_mail_schema(db_path)
    con = _db(db_path)
    try:
        row = con.execute(
            """
            SELECT id, account_id, uid, message_id, from_redacted, to_redacted,
                   subject_redacted, received_at, body_text_redacted, has_attachments
            FROM mail_messages
            WHERE tenant_id=? AND id=?
            LIMIT 1
            """,
            (tenant_id, message_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()
