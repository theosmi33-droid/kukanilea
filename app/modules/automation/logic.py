from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app, has_app_context

from app import core as legacy_core
from app.event_id_map import entity_id_int
from app.eventlog.core import event_append

CONDITION_MAX_LEN = 8 * 1024
ACTIONS_MAX_LEN = 32 * 1024
MAX_RULE_NAME = 200
MAX_RULE_SCOPE = 32
MAX_ERROR = 500
MAX_ACTIONS_DEFAULT = 50
MAX_TARGETS_PER_RULE = 25

ALLOWED_CONDITIONS = {
    "lead_overdue",
    "lead_screening_stale",
    "task_overdue",
    "lead_priority_high_unassigned",
}
ALLOWED_ACTIONS = {
    "create_task",
    "lead_add_event",
    "lead_set_priority",
    "lead_pin",
    "lead_assign",
    "lead_set_response_due",
}
LEAD_STATUS = {"new", "contacted", "qualified", "lost", "won", "screening", "ignored"}
LEAD_PRIORITY = {"normal", "high"}

_JSON_AVAILABLE: bool | None = None


def _tenant(tenant_id: str) -> str:
    t = legacy_core._effective_tenant(tenant_id) or legacy_core._effective_tenant(  # type: ignore[attr-defined]
        legacy_core.TENANT_DEFAULT
    )
    return t or "default"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _is_read_only() -> bool:
    if has_app_context():
        return bool(current_app.config.get("READ_ONLY", False))
    return False


def _ensure_writable() -> None:
    if _is_read_only():
        raise PermissionError("read_only")


def _db() -> sqlite3.Connection:
    return legacy_core._db()  # type: ignore[attr-defined]


def _run_write_txn(fn):
    return legacy_core._run_write_txn(fn)  # type: ignore[attr-defined]


def _json_dumps_canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_loads_strict(s: str, max_len: int) -> Any:
    if not isinstance(s, str):
        raise ValueError("validation_error")
    if len(s) > max_len:
        raise ValueError("validation_error")
    return json.loads(s)


def _json_functions_available() -> bool:
    global _JSON_AVAILABLE
    if _JSON_AVAILABLE is not None:
        return _JSON_AVAILABLE
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            try:
                row = con.execute("SELECT json_valid(?) AS ok", ('{"x":1}',)).fetchone()
                _JSON_AVAILABLE = bool(row and int(row["ok"] or 0) == 1)
            except Exception:
                _JSON_AVAILABLE = False
        finally:
            con.close()
    return bool(_JSON_AVAILABLE)


def _validate_json_fastpath(value: str) -> None:
    _json_loads_strict(value, max_len=max(CONDITION_MAX_LEN, ACTIONS_MAX_LEN))
    if not _json_functions_available():
        return
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            row = con.execute("SELECT json_valid(?) AS ok", (value,)).fetchone()
            if not row or int(row["ok"] or 0) != 1:
                raise ValueError("validation_error")
        finally:
            con.close()


def _new_id() -> str:
    return uuid.uuid4().hex


def _action_hash(action: dict[str, Any], target_type: str, target_id: str) -> str:
    raw = _json_dumps_canonical(
        {"action": action, "target_type": target_type, "target_id": target_id}
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_condition(kind: str, obj: dict[str, Any]) -> dict[str, Any]:
    kind_n = (kind or "").strip()
    if kind_n not in ALLOWED_CONDITIONS:
        raise ValueError("validation_error")
    if not isinstance(obj, dict):
        raise ValueError("validation_error")

    if kind_n == "lead_overdue":
        days = int(obj.get("days_overdue", 0))
        if days < 0 or days > 365:
            raise ValueError("validation_error")
        status_in = obj.get("status_in") or ["new", "contacted", "qualified"]
        priority_in = obj.get("priority_in") or ["normal", "high"]
        if not isinstance(status_in, list) or not set(status_in).issubset(LEAD_STATUS):
            raise ValueError("validation_error")
        if not isinstance(priority_in, list) or not set(priority_in).issubset(
            LEAD_PRIORITY
        ):
            raise ValueError("validation_error")
        return {
            "days_overdue": days,
            "status_in": list(status_in),
            "priority_in": list(priority_in),
        }

    if kind_n == "lead_screening_stale":
        hours = int(obj.get("hours_in_screening", 0))
        if hours < 1 or hours > 720:
            raise ValueError("validation_error")
        return {"hours_in_screening": hours}

    if kind_n == "lead_priority_high_unassigned":
        hours = int(obj.get("hours_since_created", 0))
        if hours < 0 or hours > 720:
            raise ValueError("validation_error")
        return {"hours_since_created": hours}

    days = int(obj.get("days_overdue", 0))
    if days < 0 or days > 365:
        raise ValueError("validation_error")
    status_in = obj.get("status_in") or ["OPEN"]
    if not isinstance(status_in, list):
        raise ValueError("validation_error")
    return {"days_overdue": days, "status_in": [str(x) for x in status_in]}


def validate_actions(arr: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(arr, list) or not arr:
        raise ValueError("validation_error")
    normalized: list[dict[str, Any]] = []
    for item in arr:
        if not isinstance(item, dict):
            raise ValueError("validation_error")
        kind = str(item.get("kind") or "").strip()
        if kind not in ALLOWED_ACTIONS:
            raise ValueError("validation_error")

        if kind == "create_task":
            title = str(item.get("title_template") or "").strip()
            if not title or len(title) > 300:
                raise ValueError("validation_error")
            prio = str(item.get("priority") or "MEDIUM").strip().upper()
            if prio not in {"MEDIUM", "HIGH"}:
                raise ValueError("validation_error")
            assign_to = str(item.get("assign_to") or "actor").strip()
            if len(assign_to) > 128:
                raise ValueError("validation_error")
            normalized.append(
                {
                    "kind": kind,
                    "title_template": title,
                    "priority": prio,
                    "assign_to": assign_to,
                    "link_lead_id": bool(item.get("link_lead_id", True)),
                }
            )
            continue

        if kind == "lead_pin":
            normalized.append({"kind": kind, "value": bool(item.get("value", True))})
            continue

        if kind == "lead_set_priority":
            val = str(item.get("value") or "").strip().lower()
            if val not in LEAD_PRIORITY:
                raise ValueError("validation_error")
            normalized.append({"kind": kind, "value": val})
            continue

        if kind == "lead_assign":
            val = str(item.get("value") or "").strip()
            if not val or len(val) > 128:
                raise ValueError("validation_error")
            normalized.append({"kind": kind, "value": val})
            continue

        if kind == "lead_set_response_due":
            hours = int(item.get("hours_from_now", 0))
            if hours < 1 or hours > 720:
                raise ValueError("validation_error")
            normalized.append({"kind": kind, "hours_from_now": hours})
            continue

        if kind == "lead_add_event":
            et = str(item.get("event_type") or "").strip()
            if et not in {"automation_reminder", "automation_screening"}:
                raise ValueError("validation_error")
            normalized.append({"kind": kind, "event_type": et})
            continue

    return normalized


def _select_rule_targets(
    con: sqlite3.Connection,
    tenant_id: str,
    condition_kind: str,
    condition: dict[str, Any],
    max_targets: int,
) -> list[dict[str, Any]]:
    lim = max(1, min(int(max_targets), MAX_TARGETS_PER_RULE))
    now = datetime.now(UTC)

    if condition_kind == "lead_overdue":
        cutoff = (now - timedelta(days=int(condition["days_overdue"]))).isoformat(
            timespec="seconds"
        )
        status_in = condition["status_in"]
        priority_in = condition["priority_in"]
        sql = (
            "SELECT id, status, priority, assigned_to, response_due FROM leads "
            f"WHERE tenant_id=? AND response_due IS NOT NULL AND datetime(response_due) <= datetime(?) "
            f"AND status IN ({','.join('?' for _ in status_in)}) "
            f"AND priority IN ({','.join('?' for _ in priority_in)}) "
            "ORDER BY datetime(response_due) ASC, created_at DESC LIMIT ?"
        )
        rows = con.execute(
            sql, (tenant_id, cutoff, *status_in, *priority_in, lim)
        ).fetchall()
        return [
            dict(r) | {"entity_type": "lead", "entity_id": str(r["id"])} for r in rows
        ]

    if condition_kind == "lead_screening_stale":
        cutoff = (
            now - timedelta(hours=int(condition["hours_in_screening"]))
        ).isoformat(timespec="seconds")
        rows = con.execute(
            """
            SELECT id, status, priority, assigned_to, response_due
            FROM leads
            WHERE tenant_id=? AND status='screening' AND datetime(created_at) <= datetime(?)
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (tenant_id, cutoff, lim),
        ).fetchall()
        return [
            dict(r) | {"entity_type": "lead", "entity_id": str(r["id"])} for r in rows
        ]

    if condition_kind == "lead_priority_high_unassigned":
        cutoff = (
            now - timedelta(hours=int(condition["hours_since_created"]))
        ).isoformat(timespec="seconds")
        rows = con.execute(
            """
            SELECT id, status, priority, assigned_to, response_due
            FROM leads
            WHERE tenant_id=? AND priority='high' AND (assigned_to IS NULL OR assigned_to='')
              AND datetime(created_at) <= datetime(?)
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (tenant_id, cutoff, lim),
        ).fetchall()
        return [
            dict(r) | {"entity_type": "lead", "entity_id": str(r["id"])} for r in rows
        ]

    cutoff = (now - timedelta(days=int(condition["days_overdue"]))).isoformat(
        timespec="seconds"
    )
    status_in = [str(x) for x in condition["status_in"]]
    sql = (
        "SELECT id, status, title, ts FROM tasks "
        f"WHERE tenant=? AND datetime(ts) <= datetime(?) AND status IN ({','.join('?' for _ in status_in)}) "
        "ORDER BY ts ASC, id ASC LIMIT ?"
    )
    rows = con.execute(sql, (tenant_id, cutoff, *status_in, lim)).fetchall()
    return [dict(r) | {"entity_type": "task", "entity_id": str(r["id"])} for r in rows]


def _resolve_assign_to(
    action_value: str, actor_user_id: str, lead_row: sqlite3.Row | None
) -> str | None:
    if action_value == "actor":
        return actor_user_id or None
    if action_value == "lead.assigned_to":
        if lead_row is None:
            return None
        return (
            (lead_row["assigned_to"] or "")
            if isinstance(lead_row, sqlite3.Row)
            else None
        )
    return action_value


def _apply_action(
    con: sqlite3.Connection,
    tenant_id: str,
    actor_user_id: str,
    action: dict[str, Any],
    target: dict[str, Any],
    run_id: str,
    rule_id: str,
) -> tuple[str, str | None]:
    kind = str(action["kind"])
    target_type = str(target["entity_type"])
    target_id = str(target["entity_id"])
    target_id_int = entity_id_int(target_id)
    action_hash = _action_hash(action, target_type, target_id)
    row_id = _new_id()
    now = _now_iso()

    cur = con.execute(
        """
        INSERT OR IGNORE INTO automation_run_actions(
          id, tenant_id, run_id, rule_id, target_entity_type, target_entity_id_int,
          action_kind, action_hash, status, error, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            row_id,
            tenant_id,
            run_id,
            rule_id,
            target_type,
            target_id_int,
            kind,
            action_hash,
            "skipped",
            None,
            now,
        ),
    )
    if int(cur.rowcount or 0) == 0:
        return "skipped", None

    if kind == "create_task":
        lead_short = target_id[:8]
        title_tpl = str(action["title_template"])
        title = title_tpl.replace("{lead_id_short}", lead_short)
        assignee = _resolve_assign_to(str(action["assign_to"]), actor_user_id, None)
        meta = {"automation": True}
        if action.get("link_lead_id") and target_type == "lead":
            meta["lead_id"] = target_id
        con.execute(
            """
            INSERT INTO tasks(ts, tenant, severity, task_type, status, title, details, meta_json, created_by)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                now,
                tenant_id,
                str(action["priority"]),
                "automation",
                "OPEN",
                title,
                None,
                _json_dumps_canonical(meta),
                assignee or actor_user_id,
            ),
        )
        event_append(
            event_type="automation_action_applied",
            entity_type="task",
            entity_id=entity_id_int(f"task:{tenant_id}:{title}:{now}"),
            payload={
                "schema_version": 1,
                "source": "automation/apply_action",
                "actor_user_id": "automation",
                "tenant_id": tenant_id,
                "data": {
                    "run_id": run_id,
                    "rule_id": rule_id,
                    "action_kind": kind,
                    "target_type": target_type,
                },
            },
            con=con,
        )
        return "ok", None

    if target_type != "lead":
        raise ValueError("validation_error")

    lead_row = con.execute(
        "SELECT id, priority, pinned, assigned_to FROM leads WHERE tenant_id=? AND id=?",
        (tenant_id, target_id),
    ).fetchone()
    if not lead_row:
        return "error", "not_found"

    if kind == "lead_pin":
        con.execute(
            "UPDATE leads SET pinned=?, updated_at=? WHERE tenant_id=? AND id=?",
            (1 if action["value"] else 0, now, tenant_id, target_id),
        )
    elif kind == "lead_set_priority":
        con.execute(
            "UPDATE leads SET priority=?, updated_at=? WHERE tenant_id=? AND id=?",
            (str(action["value"]), now, tenant_id, target_id),
        )
    elif kind == "lead_assign":
        assignee = _resolve_assign_to(str(action["value"]), actor_user_id, lead_row)
        con.execute(
            "UPDATE leads SET assigned_to=?, updated_at=? WHERE tenant_id=? AND id=?",
            (assignee, now, tenant_id, target_id),
        )
    elif kind == "lead_set_response_due":
        due = (
            datetime.now(UTC) + timedelta(hours=int(action["hours_from_now"]))
        ).isoformat(timespec="seconds")
        con.execute(
            "UPDATE leads SET response_due=?, updated_at=? WHERE tenant_id=? AND id=?",
            (due, now, tenant_id, target_id),
        )
    elif kind == "lead_add_event":
        pass
    else:
        raise ValueError("validation_error")

    event_append(
        event_type="automation_action_applied",
        entity_type="lead",
        entity_id=entity_id_int(target_id),
        payload={
            "schema_version": 1,
            "source": "automation/apply_action",
            "actor_user_id": "automation",
            "tenant_id": tenant_id,
            "data": {
                "run_id": run_id,
                "rule_id": rule_id,
                "action_kind": kind,
                "target_type": target_type,
            },
        },
        con=con,
    )
    return "ok", None


def automation_rule_create(
    tenant_id: str,
    name: str,
    scope: str,
    condition_kind: str,
    condition_json: str,
    action_list_json: str,
    created_by: str,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    n = (name or "").strip()
    sc = (scope or "").strip().lower()
    if not n or len(n) > MAX_RULE_NAME or not sc or len(sc) > MAX_RULE_SCOPE:
        raise ValueError("validation_error")
    if not created_by:
        raise ValueError("validation_error")

    cond_obj = _json_loads_strict(condition_json, CONDITION_MAX_LEN)
    acts_obj = _json_loads_strict(action_list_json, ACTIONS_MAX_LEN)
    cond_norm = validate_condition(condition_kind, cond_obj)
    actions_norm = validate_actions(acts_obj)
    cond_json_norm = _json_dumps_canonical(cond_norm)
    actions_json_norm = _json_dumps_canonical(actions_norm)
    _validate_json_fastpath(cond_json_norm)
    _validate_json_fastpath(actions_json_norm)

    rule_id = _new_id()
    now = _now_iso()

    def _tx(con: sqlite3.Connection) -> str:
        con.execute(
            """
            INSERT INTO automation_rules(
              id, tenant_id, enabled, name, scope, condition_kind,
              condition_json, action_list_json, created_by,
              created_at, updated_at, last_error, last_error_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rule_id,
                t,
                1,
                n,
                sc,
                condition_kind,
                cond_json_norm,
                actions_json_norm,
                created_by,
                now,
                now,
                None,
                None,
            ),
        )
        event_append(
            event_type="automation_rule_created",
            entity_type="automation_rule",
            entity_id=entity_id_int(rule_id),
            payload={
                "schema_version": 1,
                "source": "automation/rule_create",
                "actor_user_id": created_by,
                "tenant_id": t,
                "data": {
                    "rule_id": rule_id,
                    "condition_kind": condition_kind,
                    "scope": sc,
                },
            },
            con=con,
        )
        return rule_id

    return _run_write_txn(_tx)


def automation_rule_list(tenant_id: str) -> list[dict[str, Any]]:
    t = _tenant(tenant_id)
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            rows = con.execute(
                """
                SELECT id, tenant_id, enabled, name, scope, condition_kind,
                       condition_json, action_list_json, created_by,
                       created_at, updated_at, last_error, last_error_at
                FROM automation_rules
                WHERE tenant_id=?
                ORDER BY updated_at DESC, id DESC
                """,
                (t,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def automation_rule_get(tenant_id: str, rule_id: str) -> dict[str, Any] | None:
    t = _tenant(tenant_id)
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            row = con.execute(
                """
                SELECT id, tenant_id, enabled, name, scope, condition_kind,
                       condition_json, action_list_json, created_by,
                       created_at, updated_at, last_error, last_error_at
                FROM automation_rules
                WHERE tenant_id=? AND id=?
                LIMIT 1
                """,
                (t, rule_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            con.close()


def automation_rule_toggle(
    tenant_id: str, rule_id: str, enabled: bool, actor_user_id: str
) -> None:
    _ensure_writable()
    t = _tenant(tenant_id)

    def _tx(con: sqlite3.Connection) -> None:
        row = con.execute(
            "SELECT id, enabled FROM automation_rules WHERE tenant_id=? AND id=?",
            (t, rule_id),
        ).fetchone()
        if not row:
            raise ValueError("not_found")
        con.execute(
            "UPDATE automation_rules SET enabled=?, updated_at=? WHERE tenant_id=? AND id=?",
            (1 if enabled else 0, _now_iso(), t, rule_id),
        )
        event_append(
            event_type="automation_rule_toggled",
            entity_type="automation_rule",
            entity_id=entity_id_int(rule_id),
            payload={
                "schema_version": 1,
                "source": "automation/rule_toggle",
                "actor_user_id": actor_user_id,
                "tenant_id": t,
                "data": {"rule_id": rule_id, "enabled": bool(enabled)},
            },
            con=con,
        )

    _run_write_txn(_tx)


def automation_rule_disable(tenant_id: str, rule_id: str, actor_user_id: str) -> None:
    automation_rule_toggle(
        tenant_id, rule_id, enabled=False, actor_user_id=actor_user_id
    )


def _mark_rule_invalid(tenant_id: str, rule_id: str, message: str) -> None:
    t = _tenant(tenant_id)
    msg = (message or "invalid rule")[:MAX_ERROR]

    def _tx(con: sqlite3.Connection) -> None:
        con.execute(
            "UPDATE automation_rules SET enabled=0, last_error=?, last_error_at=?, updated_at=? WHERE tenant_id=? AND id=?",
            (msg, _now_iso(), _now_iso(), t, rule_id),
        )

    _run_write_txn(_tx)


def _run_insert(tenant_id: str, triggered_by: str, max_actions: int) -> str:
    run_id = _new_id()

    def _tx(con: sqlite3.Connection) -> str:
        con.execute(
            """
            INSERT INTO automation_runs(
              id, tenant_id, triggered_by, started_at, finished_at,
              status, max_actions, actions_executed, aborted_reason, warnings_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                tenant_id,
                triggered_by,
                _now_iso(),
                None,
                "running",
                max_actions,
                0,
                None,
                "[]",
            ),
        )
        return run_id

    return _run_write_txn(_tx)


def _run_update(
    tenant_id: str,
    run_id: str,
    *,
    status: str,
    actions_executed: int,
    aborted_reason: str | None,
    warnings: list[str],
) -> None:
    def _tx(con: sqlite3.Connection) -> None:
        con.execute(
            """
            UPDATE automation_runs
            SET finished_at=?, status=?, actions_executed=?, aborted_reason=?, warnings_json=?
            WHERE tenant_id=? AND id=?
            """,
            (
                _now_iso(),
                status,
                int(actions_executed),
                aborted_reason,
                _json_dumps_canonical([w[:MAX_ERROR] for w in warnings]),
                tenant_id,
                run_id,
            ),
        )

    _run_write_txn(_tx)


def automation_latest_run(tenant_id: str) -> dict[str, Any] | None:
    t = _tenant(tenant_id)
    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            row = con.execute(
                """
                SELECT id, tenant_id, triggered_by, started_at, finished_at, status,
                       max_actions, actions_executed, aborted_reason, warnings_json
                FROM automation_runs
                WHERE tenant_id=?
                ORDER BY started_at DESC, id DESC
                LIMIT 1
                """,
                (t,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            con.close()


def automation_run_now(
    tenant_id: str,
    triggered_by_user_id: str,
    max_actions: int = MAX_ACTIONS_DEFAULT,
) -> str:
    _ensure_writable()
    t = _tenant(tenant_id)
    max_actions = max(1, min(int(max_actions), 500))
    run_id = _run_insert(t, triggered_by_user_id or "system", max_actions)

    warnings: list[str] = []
    actions_executed = 0
    status = "ok"
    aborted_reason: str | None = None

    with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
        con = _db()
        try:
            rules = con.execute(
                """
                SELECT id, condition_kind, condition_json, action_list_json
                FROM automation_rules
                WHERE tenant_id=? AND enabled=1
                ORDER BY updated_at DESC, id DESC
                """,
                (t,),
            ).fetchall()
        finally:
            con.close()

    for rule in rules:
        rule_id = str(rule["id"])
        try:
            cond_raw = _json_loads_strict(
                str(rule["condition_json"]), CONDITION_MAX_LEN
            )
            acts_raw = _json_loads_strict(
                str(rule["action_list_json"]), ACTIONS_MAX_LEN
            )
            condition = validate_condition(str(rule["condition_kind"]), cond_raw)
            actions = validate_actions(acts_raw)
        except Exception:
            warnings.append(f"rule_invalid:{rule_id}")
            _mark_rule_invalid(t, rule_id, "invalid_json_or_dsl")
            continue

        with legacy_core._DB_LOCK:  # type: ignore[attr-defined]
            con = _db()
            try:
                targets = _select_rule_targets(
                    con, t, str(rule["condition_kind"]), condition, MAX_TARGETS_PER_RULE
                )
            finally:
                con.close()

        for target in targets:
            for action in actions:
                if actions_executed >= max_actions:
                    status = "aborted"
                    aborted_reason = "max_actions"
                    break

                def _tx_apply(con: sqlite3.Connection) -> tuple[str, str | None]:
                    return _apply_action(
                        con,
                        t,
                        triggered_by_user_id or "system",
                        action,
                        target,
                        run_id,
                        rule_id,
                    )

                try:
                    action_status, error = _run_write_txn(_tx_apply)
                except PermissionError:
                    status = "error"
                    aborted_reason = "read_only"
                    break
                except ValueError as exc:
                    action_status = "error"
                    error = str(exc)

                actions_executed += 1
                if action_status == "error" and error:
                    warnings.append(
                        f"action_error:{rule_id}:{action.get('kind')}:{error[:64]}"
                    )

                def _tx_update_action(con: sqlite3.Connection) -> None:
                    ah = _action_hash(
                        action, str(target["entity_type"]), str(target["entity_id"])
                    )
                    con.execute(
                        """
                        UPDATE automation_run_actions
                        SET status=?, error=?
                        WHERE tenant_id=? AND run_id=? AND rule_id=? AND action_hash=?
                        """,
                        (
                            action_status,
                            error[:MAX_ERROR] if error else None,
                            t,
                            run_id,
                            rule_id,
                            ah,
                        ),
                    )

                _run_write_txn(_tx_update_action)

            if status == "aborted":
                break
        if status == "aborted":
            break

    _run_update(
        t,
        run_id,
        status=status,
        actions_executed=actions_executed,
        aborted_reason=aborted_reason,
        warnings=warnings,
    )
    return run_id
