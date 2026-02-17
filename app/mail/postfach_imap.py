from __future__ import annotations

import hashlib
import imaplib
import ssl
from datetime import datetime, timezone
from email import message_from_bytes, policy
from typing import Any

from . import postfach_store as store


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if ctype == "text/plain":
                text_plain.append(decoded)
            elif ctype == "text/html":
                text_html.append(decoded)
    else:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        decoded = payload.decode(charset, errors="replace")
        ctype = str(msg.get_content_type() or "").lower()
        if ctype == "text/html":
            text_html.append(decoded)
        else:
            text_plain.append(decoded)

    body = "\n".join(text_plain).strip() or "\n".join(text_html).strip()
    return body, has_attachments


def connect(account: dict[str, Any]) -> imaplib.IMAP4_SSL:
    host = str(account.get("imap_host") or "").strip()
    port = int(account.get("imap_port") or 993)
    context = ssl.create_default_context()
    return imaplib.IMAP4_SSL(host, port, ssl_context=context, timeout=20)


def sync_account(
    db_path,
    *,
    tenant_id: str,
    account_id: str,
    limit: int = 50,
    since: str | None = None,
) -> dict[str, Any]:
    store.ensure_postfach_schema(db_path)
    if not store.email_encryption_ready():
        return {"ok": False, "reason": "email_encryption_key_missing", "imported": 0}

    account = store.get_account(db_path, tenant_id, account_id)
    if not account:
        return {"ok": False, "reason": "account_not_found", "imported": 0}

    try:
        password = store.decrypt_account_secret(account)
    except Exception:
        return {"ok": False, "reason": "account_secret_unavailable", "imported": 0}

    username = str(account.get("imap_username") or "").strip()
    lim = max(1, min(int(limit or 50), 200))

    cursor = str(since or account.get("sync_cursor") or "").strip()
    imported = 0
    duplicates = 0
    fetched = 0
    last_uid = cursor

    try:
        with connect(account) as imap:
            imap.login(username, password)
            imap.select("INBOX")
            status, data = imap.uid("search", None, "ALL")
            if status != "OK":
                return {
                    "ok": False,
                    "reason": "imap_search_failed",
                    "imported": imported,
                    "duplicates": duplicates,
                }
            all_uids = data[0].decode("utf-8", errors="ignore").split() if data else []
            if cursor.isdigit():
                candidate_uids = [
                    uid for uid in all_uids if uid.isdigit() and int(uid) > int(cursor)
                ]
            else:
                candidate_uids = all_uids
            uids = candidate_uids[-lim:]
            for uid in uids:
                fetched += 1
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
                message_id_header = str(msg.get("message-id") or "").strip() or None
                if not message_id_header:
                    message_id_header = (
                        "<"
                        + hashlib.sha256(raw_bytes).hexdigest()[:32]
                        + "@postfach.local>"
                    )
                in_reply_to = str(msg.get("in-reply-to") or "").strip() or None
                references_header = str(msg.get("references") or "").strip() or None

                result = store.store_message(
                    db_path,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    direction="inbound",
                    message_id_header=message_id_header,
                    in_reply_to=in_reply_to,
                    references_header=references_header,
                    from_value=str(msg.get("from") or ""),
                    to_value=str(msg.get("to") or ""),
                    subject_value=str(msg.get("subject") or ""),
                    body_value=body_raw,
                    raw_eml=raw_bytes,
                    has_attachments=bool(has_attachments),
                    received_at=str(msg.get("date") or "") or _now_iso(),
                )
                if bool(result.get("duplicate")):
                    duplicates += 1
                else:
                    imported += 1
                last_uid = uid

        if last_uid:
            store.update_account_sync_cursor(
                db_path,
                tenant_id=tenant_id,
                account_id=account_id,
                sync_cursor=last_uid,
            )

        return {
            "ok": True,
            "reason": "ok",
            "imported": imported,
            "duplicates": duplicates,
            "fetched": fetched,
            "sync_cursor": str(last_uid or ""),
        }
    except Exception:
        return {
            "ok": False,
            "reason": "imap_sync_failed",
            "imported": imported,
            "duplicates": duplicates,
            "fetched": fetched,
        }
