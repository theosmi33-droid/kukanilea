from __future__ import annotations

import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from . import postfach_oauth as oauth
from . import postfach_store as store


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _smtp_auth_with_xoauth2(smtp, *, username: str, access_token: str):
    auth_str = oauth.xoauth2_auth_string(username, access_token)
    code, resp = smtp.docmd("AUTH", "XOAUTH2 " + auth_str)
    if int(code) not in {235, 250}:
        raise RuntimeError(f"smtp_oauth_auth_failed:{code}:{resp}")


def send_draft(
    db_path,
    *,
    tenant_id: str,
    draft_id: str,
    user_confirmed: bool,
) -> dict[str, object]:
    if not bool(user_confirmed):
        return {"ok": False, "reason": "user_confirmation_required"}
    if not store.email_encryption_ready():
        return {"ok": False, "reason": "email_encryption_key_missing"}

    draft = store.get_draft(
        db_path, tenant_id=tenant_id, draft_id=draft_id, include_plain=True
    )
    if not draft:
        return {"ok": False, "reason": "draft_not_found"}
    if str(draft.get("status") or "").strip().lower() == "sent":
        return {"ok": False, "reason": "draft_already_sent"}

    account_id = str(draft.get("account_id") or "")
    account = store.get_account(db_path, tenant_id, account_id)
    if not account:
        return {"ok": False, "reason": "account_not_found"}

    auth_mode = str(account.get("auth_mode") or "password").strip().lower()
    smtp_host = str(account.get("smtp_host") or "").strip()
    smtp_port = int(account.get("smtp_port") or 465)
    smtp_username = str(account.get("smtp_username") or "").strip()
    smtp_use_ssl = bool(int(account.get("smtp_use_ssl") or 0))

    to_plain = str(draft.get("to_plain") or "").strip()
    subject_plain = str(draft.get("subject_plain") or "").strip()
    body_plain = str(draft.get("body_plain") or "").strip()

    if not to_plain or not body_plain:
        return {"ok": False, "reason": "draft_invalid"}

    msg = EmailMessage()
    msg["To"] = to_plain
    msg["From"] = smtp_username or "noreply@kukanilea.local"
    msg["Subject"] = subject_plain or "KUKANILEA Postfach"
    msg["Message-ID"] = make_msgid(domain="kukanilea.local")
    msg["Date"] = format_datetime(datetime.now(UTC))
    msg.set_content(body_plain)

    context = ssl.create_default_context()
    try:
        if auth_mode == "password":
            try:
                password = store.decrypt_account_secret(account)
            except Exception:
                return {"ok": False, "reason": "account_secret_unavailable"}
            if smtp_use_ssl:
                with smtplib.SMTP_SSL(
                    smtp_host, smtp_port, timeout=20, context=context
                ) as smtp:
                    smtp.login(smtp_username, password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    smtp.login(smtp_username, password)
                    smtp.send_message(msg)
        else:
            provider = str(account.get("oauth_provider") or "").strip().lower()
            token = store.get_oauth_token(
                db_path,
                tenant_id=tenant_id,
                account_id=account_id,
                provider=provider or None,
            )
            if not token:
                return {"ok": False, "reason": "oauth_token_missing"}
            access_token = str(token.get("access_token") or "").strip()
            if not access_token:
                return {"ok": False, "reason": "oauth_access_token_missing"}

            if smtp_use_ssl:
                with smtplib.SMTP_SSL(
                    smtp_host, smtp_port, timeout=20, context=context
                ) as smtp:
                    _smtp_auth_with_xoauth2(
                        smtp,
                        username=smtp_username,
                        access_token=access_token,
                    )
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    _smtp_auth_with_xoauth2(
                        smtp,
                        username=smtp_username,
                        access_token=access_token,
                    )
                    smtp.send_message(msg)
    except Exception:
        return {"ok": False, "reason": "smtp_send_failed"}

    store.mark_draft_sent(db_path, tenant_id=tenant_id, draft_id=draft_id)
    stored = store.store_message(
        db_path,
        tenant_id=tenant_id,
        account_id=account_id,
        direction="outbound",
        message_id_header=str(msg.get("Message-ID") or "").strip() or None,
        in_reply_to=None,
        references_header=None,
        from_value=str(msg.get("From") or ""),
        to_value=str(msg.get("To") or ""),
        subject_value=str(msg.get("Subject") or ""),
        body_value=body_plain,
        raw_eml=msg.as_bytes(),
        has_attachments=False,
        received_at=_now_iso(),
    )

    return {
        "ok": True,
        "reason": "ok",
        "draft_id": draft_id,
        "thread_id": stored.get("thread_id"),
        "message_id": stored.get("message_id"),
    }
