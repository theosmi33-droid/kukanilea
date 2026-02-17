from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import kukanilea_core_v3_fixed as core
from app.mail import postfach_create_draft, postfach_create_followup_task

from .store import create_pending_action

ALLOWLIST_ACTIONS = {"create_task", "create_postfach_draft", "create_followup"}
NON_DESTRUCTIVE_DIRECT = {"create_task", "create_followup"}
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
}


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


def execute_action(
    *,
    tenant_id: str,
    rule_id: str,
    action_config: Mapping[str, Any],
    context: Mapping[str, Any],
    db_path: Path | str | None = None,
    user_confirmed: bool = False,
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
