from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import kukanilea_core_v3_fixed as core
from app.mail import (
    postfach_create_draft,
    postfach_create_followup_task,
    postfach_get_oauth_token,
    postfach_list_accounts,
    postfach_oauth_token_expired,
    postfach_safety_check_draft,
    postfach_send_draft,
)
from app.webhooks import execute_webhook_action

from .store import create_pending_action

ALLOWLIST_ACTIONS = {
    "create_task",
    "create_postfach_draft",
    "create_followup",
    "email_draft",
    "email_send",
    "webhook",
}
NON_DESTRUCTIVE_DIRECT = {"create_task", "create_followup"}
EMAIL_ALLOWED_PLACEHOLDERS = {
    "customer_name",
    "event_type",
    "trigger_ref",
    "thread_id",
    "entity_id",
    "tenant_id",
}
SNAPSHOT_ALLOWLIST = {
    "event_id",
    "event_type",
    "entity_type",
    "entity_id",
    "tenant_id",
    "trigger_ref",
    "thread_id",
    "account_id",
    "source",
    "customer_name",
    "lead_id",
    "case_id",
}
_TEMPLATE_VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_TEMPLATE_VAR_DOUBLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
EMAIL_SUBJECT_MAX_LENGTH = 255
EMAIL_BODY_MAX_LENGTH = 20000


def _resolve_db_path(db_path: Path | str | None) -> Path:
    if db_path is None:
        return Path(core.DB_PATH)
    return Path(db_path)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalized_action(
    action_config: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    cfg = dict(action_config or {})
    action_type = str(cfg.get("action_type") or cfg.get("type") or "").strip().lower()
    return action_type, cfg


def _context_snapshot(context: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in SNAPSHOT_ALLOWLIST:
        if key in context:
            out[key] = str(context.get(key) or "")
    return out


def _requires_confirm(
    action_type: str, action_cfg: Mapping[str, Any], user_confirmed: bool
) -> bool:
    if action_type == "create_postfach_draft":
        return not bool(user_confirmed)
    if action_type == "email_draft":
        return not bool(user_confirmed)
    if action_type == "email_send":
        return not bool(user_confirmed)
    if action_type == "webhook":
        return False
    configured = bool(action_cfg.get("requires_confirm", True))
    if configured:
        return not bool(user_confirmed)
    if action_type in NON_DESTRUCTIVE_DIRECT:
        return False
    return not bool(user_confirmed)


def _execute_create_task(
    *,
    tenant_id: str,
    rule_id: str,
    action_cfg: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    title = (
        str(action_cfg.get("title") or "").strip() or f"Automation Task {rule_id[:8]}"
    )
    details = str(action_cfg.get("details") or "").strip()
    trigger_ref = str(context.get("trigger_ref") or "").strip()
    created_by = str(action_cfg.get("created_by") or "automation").strip()
    token = f"automation:{rule_id}:{trigger_ref or 'manual'}"
    task_id = int(
        core.task_create(
            tenant=tenant_id,
            severity="INFO",
            task_type="AUTOMATION",
            title=title,
            details=details,
            token=token,
            meta={"source": "automation_builder", "rule_id": rule_id},
            created_by=created_by,
        )
    )
    return {"status": "ok", "result": {"task_id": task_id}}


def _execute_create_followup(
    *,
    tenant_id: str,
    rule_id: str,
    action_cfg: Mapping[str, Any],
    context: Mapping[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    thread_id = str(
        action_cfg.get("thread_id") or context.get("thread_id") or ""
    ).strip()
    if not thread_id:
        # Fallback: no thread reference, create a generic task.
        return _execute_create_task(
            tenant_id=tenant_id,
            rule_id=rule_id,
            action_cfg={
                "title": str(action_cfg.get("title") or "Automation Follow-up"),
                "details": str(action_cfg.get("details") or ""),
                "created_by": str(action_cfg.get("created_by") or "automation"),
            },
            context=context,
        )
    created_by = str(action_cfg.get("created_by") or "automation").strip()
    owner = str(action_cfg.get("owner") or "unassigned").strip()
    due_at = str(action_cfg.get("due_at") or "").strip()
    title = str(action_cfg.get("title") or "Postfach Follow-up").strip()
    result = postfach_create_followup_task(
        db_path,
        tenant_id=tenant_id,
        thread_id=thread_id,
        due_at=due_at,
        owner=owner,
        title=title,
        created_by=created_by,
    )
    return {"status": "ok", "result": result}


def _execute_create_postfach_draft(
    *,
    tenant_id: str,
    action_cfg: Mapping[str, Any],
    context: Mapping[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    account_id = str(
        action_cfg.get("account_id") or context.get("account_id") or ""
    ).strip()
    if not account_id:
        return {"status": "failed", "error": "account_id_required"}
    draft_id = postfach_create_draft(
        db_path,
        tenant_id=tenant_id,
        account_id=account_id,
        thread_id=str(
            action_cfg.get("thread_id") or context.get("thread_id") or ""
        ).strip()
        or None,
        to_value=str(action_cfg.get("to") or "").strip(),
        subject_value=str(action_cfg.get("subject") or "").strip(),
        body_value=str(action_cfg.get("body") or "").strip(),
    )
    return {"status": "ok", "result": {"draft_id": draft_id}}


def _split_recipients(raw: Any) -> list[str]:
    if isinstance(raw, list):
        candidates = [str(item or "").strip() for item in raw]
    else:
        text = str(raw or "")
        normalized = text.replace(";", ",").replace("\n", ",")
        candidates = [part.strip() for part in normalized.split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        if not value:
            continue
        email = value.lower()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            continue
        if email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


def _crm_recipients_exist(
    *, db_path: Path, tenant_id: str, recipients: list[str]
) -> bool:
    if not recipients:
        return False

    def _read_found(con: sqlite3.Connection, table: str) -> set[str]:
        table_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        if table_exists is None:
            return set()
        cols = {
            str(row["name"] or "")
            for row in con.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if "tenant_id" not in cols or "email" not in cols:
            return set()
        placeholders = ",".join(["?"] * len(recipients))
        rows = con.execute(
            f"""
            SELECT LOWER(TRIM(email)) AS email_norm
            FROM {table}
            WHERE tenant_id=?
              AND email IS NOT NULL
              AND LOWER(TRIM(email)) IN ({placeholders})
            """,
            (tenant_id, *recipients),
        ).fetchall()
        return {str(row["email_norm"] or "").strip() for row in rows}

    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        found = _read_found(con, "contacts") | _read_found(con, "users")
        return set(recipients).issubset(found)
    except sqlite3.OperationalError:
        return False
    finally:
        con.close()


def _first_account_id(db_path: Path, tenant_id: str) -> str:
    rows = postfach_list_accounts(db_path, tenant_id)
    if not rows:
        return ""
    return str(rows[0].get("id") or "").strip()


def _extract_template_vars(template: str) -> set[str]:
    text = str(template or "")
    names = set(_TEMPLATE_VAR_PATTERN.findall(text))
    names.update(_TEMPLATE_VAR_DOUBLE_PATTERN.findall(text))
    return {str(name or "").strip() for name in names if str(name or "").strip()}


def _validate_template_vars(template: str, *, allowed: set[str]) -> bool:
    names = _extract_template_vars(template)
    return names.issubset(allowed)


def _render_email_template_text(template: str, context: Mapping[str, Any]) -> str:
    rendered = str(template or "")
    for key in EMAIL_ALLOWED_PLACEHOLDERS:
        value = str(context.get(key) or "")
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _execute_email_draft(
    *,
    tenant_id: str,
    action_cfg: Mapping[str, Any],
    context: Mapping[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    recipients = _split_recipients(action_cfg.get("to"))
    if not recipients:
        return {"status": "failed", "error": "recipient_required"}
    if not _crm_recipients_exist(
        db_path=db_path, tenant_id=tenant_id, recipients=recipients
    ):
        return {"status": "failed", "error": "recipient_not_in_crm"}

    account_id = str(
        action_cfg.get("account_id") or context.get("account_id") or ""
    ).strip() or _first_account_id(db_path, tenant_id)
    if not account_id:
        return {"status": "failed", "error": "account_not_configured"}

    doc_ids = _normalize_doc_ids(action_cfg.get("attachments"))
    if doc_ids and not _docs_exist(
        db_path=db_path, tenant_id=tenant_id, doc_ids=doc_ids
    ):
        return {"status": "failed", "error": "attachments_invalid"}

    subject = str(action_cfg.get("subject") or "").strip()
    body_template = str(action_cfg.get("body_template") or action_cfg.get("body") or "")
    if not subject or not body_template:
        return {"status": "failed", "error": "payload_invalid"}
    if len(subject) > EMAIL_SUBJECT_MAX_LENGTH:
        return {"status": "failed", "error": "subject_too_long"}
    if not _validate_template_vars(body_template, allowed=EMAIL_ALLOWED_PLACEHOLDERS):
        return {"status": "failed", "error": "template_variables_not_allowed"}
    body = _render_email_template_text(body_template, context)
    if len(body) > EMAIL_BODY_MAX_LENGTH:
        return {"status": "failed", "error": "body_too_long"}
    thread_id = (
        str(action_cfg.get("thread_id") or context.get("thread_id") or "").strip()
        or None
    )
    draft_id = postfach_create_draft(
        db_path,
        tenant_id=tenant_id,
        account_id=account_id,
        thread_id=thread_id,
        to_value=", ".join(recipients),
        subject_value=subject,
        body_value=body,
    )
    safety = postfach_safety_check_draft(
        db_path, tenant_id=tenant_id, draft_id=str(draft_id)
    )
    warning_codes: list[str] = []
    if bool(safety.get("ok")):
        for warning in safety.get("warnings") or []:
            code = str((warning or {}).get("code") or "").strip()
            if code:
                warning_codes.append(code)
    result: dict[str, Any] = {"draft_id": draft_id, "warning_count": len(warning_codes)}
    if warning_codes:
        result["warning_codes"] = warning_codes[:10]
    return {"status": "ok", "result": result}


def _normalize_doc_ids(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = [str(item or "").strip() for item in raw]
    else:
        values = [part.strip() for part in str(raw or "").replace(";", ",").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _docs_exist(*, db_path: Path, tenant_id: str, doc_ids: list[str]) -> bool:
    if not doc_ids:
        return True

    def _read_ids(
        con: sqlite3.Connection,
        *,
        table: str,
        id_column: str,
    ) -> set[str]:
        table_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        if table_exists is None:
            return set()
        cols = {
            str(row["name"] or "")
            for row in con.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if "tenant_id" not in cols or id_column not in cols:
            return set()
        placeholders = ",".join(["?"] * len(doc_ids))
        rows = con.execute(
            f"""
            SELECT {id_column} AS id_value
            FROM {table}
            WHERE tenant_id=?
              AND {id_column} IN ({placeholders})
            """,
            (tenant_id, *doc_ids),
        ).fetchall()
        return {str(row["id_value"] or "").strip() for row in rows}

    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        found = _read_ids(con, table="docs", id_column="doc_id") | _read_ids(
            con, table="documents", id_column="id"
        )
        return set(doc_ids).issubset(found)
    except sqlite3.OperationalError:
        return False
    finally:
        con.close()


def _select_oauth_account(
    *,
    db_path: Path,
    tenant_id: str,
    preferred_account_id: str = "",
) -> str:
    accounts = postfach_list_accounts(db_path, tenant_id)
    preferred = str(preferred_account_id or "").strip()
    if preferred:
        accounts = sorted(
            accounts,
            key=lambda row: 0 if str(row.get("id") or "") == preferred else 1,
        )
    for account in accounts:
        account_id = str(account.get("id") or "").strip()
        if not account_id:
            continue
        auth_mode = str(account.get("auth_mode") or "").strip().lower()
        if auth_mode not in {"oauth_google", "oauth_microsoft"}:
            continue
        provider = str(account.get("oauth_provider") or "").strip().lower() or None
        token = postfach_get_oauth_token(
            db_path,
            tenant_id=tenant_id,
            account_id=account_id,
            provider=provider,
        )
        if not token:
            continue
        expires_at = str(token.get("expires_at") or "").strip()
        if postfach_oauth_token_expired(expires_at):
            continue
        return account_id
    return ""


def _prepare_email_send(
    *,
    tenant_id: str,
    action_cfg: Mapping[str, Any],
    context: Mapping[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    recipients = _split_recipients(action_cfg.get("to"))
    if not recipients:
        return {"ok": False, "reason": "recipient_required"}
    if not _crm_recipients_exist(
        db_path=db_path, tenant_id=tenant_id, recipients=recipients
    ):
        return {"ok": False, "reason": "recipient_not_in_crm"}

    doc_ids = _normalize_doc_ids(action_cfg.get("attachments"))
    if doc_ids and not _docs_exist(
        db_path=db_path, tenant_id=tenant_id, doc_ids=doc_ids
    ):
        return {"ok": False, "reason": "attachments_invalid"}

    account_id = _select_oauth_account(
        db_path=db_path,
        tenant_id=tenant_id,
        preferred_account_id=str(
            action_cfg.get("account_id") or context.get("account_id") or ""
        ),
    )
    if not account_id:
        return {"ok": False, "reason": "oauth_account_unavailable"}

    subject = str(action_cfg.get("subject") or "").strip()
    body_template = str(action_cfg.get("body_template") or action_cfg.get("body") or "")
    if not _validate_template_vars(body_template, allowed=EMAIL_ALLOWED_PLACEHOLDERS):
        return {"ok": False, "reason": "template_variables_not_allowed"}
    body = _render_email_template_text(body_template, context)
    if not subject or not body:
        return {"ok": False, "reason": "payload_invalid"}
    if len(subject) > EMAIL_SUBJECT_MAX_LENGTH:
        return {"ok": False, "reason": "subject_too_long"}
    if len(body) > EMAIL_BODY_MAX_LENGTH:
        return {"ok": False, "reason": "body_too_long"}

    return {
        "ok": True,
        "account_id": account_id,
        "to": recipients,
        "subject": subject[:255],
        "body": body[:20000],
        "thread_id": str(
            action_cfg.get("thread_id") or context.get("thread_id") or ""
        ).strip()
        or None,
        "attachments": doc_ids,
    }


def _execute_email_send(
    *,
    tenant_id: str,
    prepared: Mapping[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    draft_id = postfach_create_draft(
        db_path,
        tenant_id=tenant_id,
        account_id=str(prepared.get("account_id") or "").strip(),
        thread_id=prepared.get("thread_id"),
        to_value=", ".join([str(v) for v in (prepared.get("to") or [])]),
        subject_value=str(prepared.get("subject") or ""),
        body_value=str(prepared.get("body") or ""),
    )
    send_result = postfach_send_draft(
        db_path,
        tenant_id=tenant_id,
        draft_id=draft_id,
        user_confirmed=True,
    )
    if not bool(send_result.get("ok")):
        return {
            "status": "failed",
            "error": str(send_result.get("reason") or "send_failed"),
        }
    return {
        "status": "ok",
        "result": {
            "draft_id": draft_id,
            "thread_id": str(send_result.get("thread_id") or ""),
            "message_id": str(send_result.get("message_id") or ""),
        },
    }


def execute_action(
    *,
    tenant_id: str,
    rule_id: str,
    action_config: Mapping[str, Any],
    context: Mapping[str, Any],
    db_path: Path | str | None = None,
    user_confirmed: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    rid = str(rule_id or "").strip()
    if not tenant or not rid:
        raise ValueError("validation_error")
    action_type, action_cfg = _normalized_action(action_config)
    if action_type not in ALLOWLIST_ACTIONS:
        return {
            "status": "failed",
            "error": "action_not_allowed",
            "action_type": action_type,
        }

    db_resolved = _resolve_db_path(db_path)
    prepared_email_send: dict[str, Any] | None = None
    if action_type == "email_send":
        prepared = _prepare_email_send(
            tenant_id=tenant,
            action_cfg=action_cfg,
            context=context,
            db_path=db_resolved,
        )
        if not bool(prepared.get("ok")):
            return {
                "status": "failed",
                "error": str(prepared.get("reason") or "validation_error"),
            }
        prepared_email_send = prepared
    if bool(dry_run):
        if _requires_confirm(action_type, action_cfg, user_confirmed):
            return {
                "status": "pending",
                "action_type": action_type,
                "result": {"dry_run": True, "requires_confirm": True},
            }
        return {
            "status": "ok",
            "action_type": action_type,
            "result": {"dry_run": True, "requires_confirm": False},
        }

    if _requires_confirm(action_type, action_cfg, user_confirmed):
        pending_id = create_pending_action(
            tenant_id=tenant,
            rule_id=rid,
            action_type=action_type,
            action_config={"action_type": action_type, **action_cfg},
            context_snapshot=_context_snapshot(context),
            db_path=db_resolved,
        )
        return {
            "status": "pending",
            "pending_id": pending_id,
            "action_type": action_type,
        }

    if action_type == "create_task":
        return _execute_create_task(
            tenant_id=tenant, rule_id=rid, action_cfg=action_cfg, context=context
        )
    if action_type == "create_followup":
        return _execute_create_followup(
            tenant_id=tenant,
            rule_id=rid,
            action_cfg=action_cfg,
            context=context,
            db_path=db_resolved,
        )
    if action_type == "create_postfach_draft":
        return _execute_create_postfach_draft(
            tenant_id=tenant,
            action_cfg=action_cfg,
            context=context,
            db_path=db_resolved,
        )
    if action_type == "email_draft":
        return _execute_email_draft(
            tenant_id=tenant,
            action_cfg=action_cfg,
            context=context,
            db_path=db_resolved,
        )
    if action_type == "email_send":
        if prepared_email_send is None:
            return {"status": "failed", "error": "validation_error"}
        return _execute_email_send(
            tenant_id=tenant,
            prepared=prepared_email_send,
            db_path=db_resolved,
        )
    if action_type == "webhook":
        return execute_webhook_action(action_cfg=action_cfg, context=context)

    return {
        "status": "failed",
        "error": "action_not_allowed",
        "action_type": action_type,
    }


def run_rule_actions(
    *,
    tenant_id: str,
    rule_id: str,
    actions: list[Mapping[str, Any]],
    context: Mapping[str, Any],
    db_path: Path | str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    executed = 0
    pending = 0
    failed = 0
    details: list[dict[str, Any]] = []
    for action in actions:
        outcome = execute_action(
            tenant_id=tenant_id,
            rule_id=rule_id,
            action_config=action,
            context=context,
            db_path=db_path,
            user_confirmed=False,
            dry_run=dry_run,
        )
        details.append(outcome)
        status = str(outcome.get("status") or "").strip().lower()
        if status == "ok":
            executed += 1
        elif status == "pending":
            pending += 1
        else:
            failed += 1
    return {
        "ok": failed == 0,
        "executed": executed,
        "pending": pending,
        "failed": failed,
        "details": details,
        "summary_redacted": _canonical(
            {"executed": executed, "pending": pending, "failed": failed}
        ),
    }
