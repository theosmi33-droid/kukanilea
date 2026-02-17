from __future__ import annotations

import hashlib
import imaplib
import os
import ssl
import time
from datetime import datetime, timezone
from email import message_from_bytes, policy
from typing import Any

from . import postfach_oauth as oauth
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


def _oauth_client_env(provider: str) -> tuple[str, str]:
    p = str(provider or "").strip().lower()
    if p == "google":
        return (
            str(os.environ.get("GOOGLE_CLIENT_ID", "") or "").strip(),
            str(os.environ.get("GOOGLE_CLIENT_SECRET", "") or "").strip(),
        )
    return (
        str(os.environ.get("MICROSOFT_CLIENT_ID", "") or "").strip(),
        str(os.environ.get("MICROSOFT_CLIENT_SECRET", "") or "").strip(),
    )


def _resolve_auth(
    db_path,
    *,
    tenant_id: str,
    account: dict[str, Any],
) -> dict[str, Any]:
    auth_mode = str(account.get("auth_mode") or "password").strip().lower()
    username = str(account.get("imap_username") or "").strip()
    if auth_mode == "password":
        try:
            password = store.decrypt_account_secret(account)
        except Exception:
            return {"ok": False, "reason": "account_secret_unavailable"}
        return {
            "ok": True,
            "kind": "password",
            "username": username,
            "password": password,
        }

    provider = str(account.get("oauth_provider") or "").strip().lower()
    if not provider:
        provider = "google" if auth_mode == "oauth_google" else "microsoft"

    token = store.get_oauth_token(
        db_path,
        tenant_id=tenant_id,
        account_id=str(account.get("id") or ""),
        provider=provider,
    )
    if not token:
        store.set_account_oauth_state(
            db_path,
            tenant_id=tenant_id,
            account_id=str(account.get("id") or ""),
            oauth_status="error",
            oauth_last_error="oauth_token_missing",
            oauth_provider=provider,
        )
        return {"ok": False, "reason": "oauth_token_missing"}

    if store.oauth_token_expired(str(token.get("expires_at") or "")):
        refresh_token = str(token.get("refresh_token") or "").strip()
        if not refresh_token:
            store.set_account_oauth_state(
                db_path,
                tenant_id=tenant_id,
                account_id=str(account.get("id") or ""),
                oauth_status="expired",
                oauth_last_error="oauth_refresh_token_missing",
                oauth_provider=provider,
            )
            return {"ok": False, "reason": "oauth_refresh_token_missing"}
        client_id, client_secret = _oauth_client_env(provider)
        if not client_id:
            store.set_account_oauth_state(
                db_path,
                tenant_id=tenant_id,
                account_id=str(account.get("id") or ""),
                oauth_status="error",
                oauth_last_error="oauth_client_not_configured",
                oauth_provider=provider,
            )
            return {"ok": False, "reason": "oauth_client_not_configured"}
        try:
            refreshed = oauth.refresh_access_token(
                provider=provider,
                client_id=client_id,
                client_secret=client_secret or None,
                refresh_token=refresh_token,
                scopes=token.get("scopes") or [],
            )
            store.save_oauth_token(
                db_path,
                tenant_id=tenant_id,
                account_id=str(account.get("id") or ""),
                provider=provider,
                access_token=str(refreshed.get("access_token") or ""),
                refresh_token=str(refreshed.get("refresh_token") or refresh_token),
                expires_at=str(refreshed.get("expires_at") or ""),
                scopes=[str(s) for s in (refreshed.get("scopes") or [])],
                token_type=str(refreshed.get("token_type") or "Bearer"),
            )
            store.set_account_oauth_state(
                db_path,
                tenant_id=tenant_id,
                account_id=str(account.get("id") or ""),
                oauth_status="connected",
                oauth_last_error="",
                oauth_provider=provider,
                oauth_scopes=[str(s) for s in (refreshed.get("scopes") or [])],
            )
            token = store.get_oauth_token(
                db_path,
                tenant_id=tenant_id,
                account_id=str(account.get("id") or ""),
                provider=provider,
            )
        except Exception:
            store.set_account_oauth_state(
                db_path,
                tenant_id=tenant_id,
                account_id=str(account.get("id") or ""),
                oauth_status="error",
                oauth_last_error="oauth_refresh_failed",
                oauth_provider=provider,
            )
            return {"ok": False, "reason": "oauth_refresh_failed"}

    access_token = str((token or {}).get("access_token") or "").strip()
    if not access_token:
        return {"ok": False, "reason": "oauth_access_token_missing"}

    store.set_account_oauth_state(
        db_path,
        tenant_id=tenant_id,
        account_id=str(account.get("id") or ""),
        oauth_status="connected",
        oauth_last_error="",
        oauth_provider=provider,
        oauth_scopes=[str(s) for s in ((token or {}).get("scopes") or [])],
    )
    return {
        "ok": True,
        "kind": "xoauth2",
        "username": username,
        "access_token": access_token,
    }


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

    auth = _resolve_auth(db_path, tenant_id=tenant_id, account=account)
    if not bool(auth.get("ok")):
        store.update_account_sync_report(
            db_path,
            tenant_id=tenant_id,
            account_id=account_id,
            ok=False,
            imported=0,
            duplicates=0,
            error_reason=str(auth.get("reason") or "auth_failed"),
        )
        return {
            "ok": False,
            "reason": str(auth.get("reason") or "auth_failed"),
            "imported": 0,
        }

    username = str(auth.get("username") or "")
    lim = max(1, min(int(limit or 50), 200))

    cursor = str(since or account.get("sync_cursor") or "").strip()
    imported = 0
    duplicates = 0
    fetched = 0
    failures = 0
    last_uid = cursor

    try:
        with connect(account) as imap:
            if str(auth.get("kind") or "") == "password":
                imap.login(username, str(auth.get("password") or ""))
            else:
                xoauth = oauth.xoauth2_auth_string(
                    username, str(auth.get("access_token") or "")
                )
                imap.authenticate("XOAUTH2", lambda _: xoauth.encode("utf-8"))

            imap.select("INBOX")
            status, data = imap.uid("search", None, "ALL")
            if status != "OK":
                store.update_account_sync_report(
                    db_path,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    ok=False,
                    imported=imported,
                    duplicates=duplicates,
                    error_reason="imap_search_failed",
                )
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
                msg_data = None
                f_status = "NO"
                for attempt in range(3):
                    f_status, msg_data = imap.uid("fetch", uid, "(RFC822)")
                    if f_status == "OK" and msg_data:
                        break
                    time.sleep(0.2 * (2**attempt))
                if f_status != "OK" or not msg_data:
                    failures += 1
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
                    failures += 1
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

        store.update_account_sync_report(
            db_path,
            tenant_id=tenant_id,
            account_id=account_id,
            ok=True,
            imported=imported,
            duplicates=duplicates,
            error_reason="" if failures == 0 else f"fetch_failures:{failures}",
        )
        automation_result: dict[str, Any] = {"ok": False, "reason": "not_run"}
        try:
            from app.automation.runner import process_events_for_tenant

            automation_result = process_events_for_tenant(
                tenant_id=tenant_id,
                db_path=db_path,
                source="eventlog",
            )
        except Exception:
            automation_result = {"ok": False, "reason": "automation_runner_failed"}
        return {
            "ok": True,
            "reason": "ok",
            "imported": imported,
            "duplicates": duplicates,
            "fetched": fetched,
            "failed_fetches": failures,
            "sync_cursor": str(last_uid or ""),
            "automation": automation_result,
        }
    except Exception:
        store.update_account_sync_report(
            db_path,
            tenant_id=tenant_id,
            account_id=account_id,
            ok=False,
            imported=imported,
            duplicates=duplicates,
            error_reason="imap_sync_failed",
        )
        return {
            "ok": False,
            "reason": "imap_sync_failed",
            "imported": imported,
            "duplicates": duplicates,
            "fetched": fetched,
            "failed_fetches": failures,
        }
