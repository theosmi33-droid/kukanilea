from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from app import core
from app.mail import (
    postfach_generate_local_ai_reply_draft,
    postfach_get_draft,
    postfach_get_thread,
    postfach_search_messages,
    postfach_send_draft,
)
from app.rate_limit import send_limiter

logger = logging.getLogger("kukanilea.mail.ai_actions")

_IDEMPOTENCY_RESULTS: dict[str, dict[str, Any]] = {}
_IDEMPOTENCY_LOCK = threading.Lock()


def _db_path() -> Path:
    return Path(core.DB_PATH)


def _tenant(payload: dict[str, Any]) -> str:
    return str(payload.get("tenant_id") or "KUKANILEA").strip() or "KUKANILEA"


def _safe_error(code: str) -> dict[str, Any]:
    return {"ok": False, "error": code}


def email_search_action(payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _tenant(payload)
    query = str(payload.get("query") or "").strip()
    account_id = str(payload.get("account_id") or "").strip() or None
    if not query:
        return _safe_error("query_required")
    try:
        rows = postfach_search_messages(
            _db_path(),
            tenant_id=tenant_id,
            account_id=account_id,
            query=query,
            limit=int(payload.get("limit") or 25),
        )
        compact = [
            {
                "id": str(row.get("id") or ""),
                "thread_id": str(row.get("thread_id") or ""),
                "subject": str(row.get("subject_redacted") or ""),
                "from": str(row.get("from_redacted") or ""),
                "received_at": str(row.get("received_at") or ""),
            }
            for row in rows
        ]
        return {"ok": True, "count": len(compact), "messages": compact}
    except Exception:
        logger.exception("email_search_action_failed")
        return _safe_error("search_unavailable")


def email_summarize_thread_action(payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _tenant(payload)
    thread_id = str(payload.get("thread_id") or "").strip()
    if not thread_id:
        return _safe_error("thread_id_required")
    try:
        thread = postfach_get_thread(_db_path(), tenant_id=tenant_id, thread_id=thread_id)
        if not thread:
            return _safe_error("thread_not_found")
        messages = thread.get("messages") if isinstance(thread.get("messages"), list) else []
        inbound = [m for m in messages if str(m.get("direction") or "") == "inbound"]
        last = messages[-1] if messages else {}
        summary = {
            "thread_id": thread_id,
            "subject": str((thread.get("thread") or {}).get("subject_redacted") or ""),
            "message_count": len(messages),
            "inbound_count": len(inbound),
            "latest_excerpt": str(last.get("redacted_text") or "")[:240],
        }
        return {"ok": True, "summary": summary}
    except Exception:
        logger.exception("email_summarize_thread_action_failed")
        return _safe_error("summary_unavailable")


def email_draft_reply_action(payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _tenant(payload)
    thread_id = str(payload.get("thread_id") or "").strip()
    if not thread_id:
        return _safe_error("thread_id_required")
    try:
        result = postfach_generate_local_ai_reply_draft(
            _db_path(),
            tenant_id=tenant_id,
            thread_id=thread_id,
            account_id=str(payload.get("account_id") or "").strip() or None,
            instruction=str(payload.get("instruction") or "").strip(),
        )
        if not bool(result.get("ok")):
            return _safe_error(str(result.get("reason") or "draft_unavailable"))
        draft_id = str(result.get("draft_id") or "")
        draft = postfach_get_draft(_db_path(), tenant_id=tenant_id, draft_id=draft_id, include_plain=True)
        return {
            "ok": True,
            "draft": {
                "draft_id": draft_id,
                "thread_id": str(result.get("thread_id") or ""),
                "to": str((draft or {}).get("to_plain") or ""),
                "subject": str((draft or {}).get("subject_plain") or ""),
                "body": str((draft or {}).get("body_plain") or ""),
                "send_allowed": False,
            },
        }
    except Exception:
        logger.exception("email_draft_reply_action_failed")
        return _safe_error("draft_unavailable")


def email_send_reply_action(payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _tenant(payload)
    draft_id = str(payload.get("draft_id") or "").strip()
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if not draft_id:
        return _safe_error("draft_id_required")
    if not idempotency_key:
        return _safe_error("idempotency_key_required")
    if not bool(payload.get("confirm")):
        return {"ok": False, "error": "confirm_required", "high_risk": True}

    dedupe_key = f"{tenant_id}:{draft_id}:{idempotency_key}"
    with _IDEMPOTENCY_LOCK:
        existing = _IDEMPOTENCY_RESULTS.get(dedupe_key)
        if existing is not None:
            return {**existing, "idempotent_replay": True}

    if not send_limiter.allow(tenant_id):
        return _safe_error("rate_limited")

    try:
        result = postfach_send_draft(
            _db_path(),
            tenant_id=tenant_id,
            draft_id=draft_id,
            user_confirmed=True,
        )
        if not bool(result.get("ok")):
            response = _safe_error(str(result.get("reason") or "send_unavailable"))
        else:
            response = {
                "ok": True,
                "draft_id": draft_id,
                "thread_id": str(result.get("thread_id") or ""),
                "message_id": str(result.get("message_id") or ""),
                "high_risk": True,
            }
        with _IDEMPOTENCY_LOCK:
            _IDEMPOTENCY_RESULTS[dedupe_key] = dict(response)
        return response
    except Exception:
        logger.exception("email_send_reply_action_failed")
        return _safe_error("send_unavailable")
