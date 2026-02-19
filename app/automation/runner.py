from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import kukanilea_core_v3_fixed as core

from .actions import run_rule_actions
from .conditions import evaluate_conditions
from .cron import cron_match, cron_minute_ref
from .store import (
    append_execution_log,
    count_execution_logs_since,
    get_rule,
    get_state_cursor,
    list_rules,
    update_execution_log,
    upsert_state_cursor,
)

EVENTLOG_SOURCE = "eventlog"
CRON_SOURCE = "cron"
CONTEXT_ALLOWLIST = {
    "event_id",
    "event_type",
    "entity_type",
    "entity_id",
    "tenant_id",
    "timestamp",
    "trigger_ref",
    "source",
    "from_domain",
    "thread_id",
    "account_id",
    "lead_id",
    "case_id",
    "source_kind",
    "source_action",
    "task_status",
    "intent",
    "cron_expression",
    "scheduled_minute",
}

_CRON_CHECKER_LOCK = threading.Lock()
_CRON_CHECKER: "CronChecker | None" = None


def _resolve_db_path(db_path: Path | str | None) -> Path:
    if db_path is None:
        return Path(core.DB_PATH)
    return Path(db_path)


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    con.execute("PRAGMA busy_timeout=5000;")
    return con


def _safe_json_loads(raw: str) -> dict[str, Any]:
    try:
        loaded = json.loads(raw or "{}")
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _payload_value(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    nested = payload.get("data")
    if isinstance(nested, Mapping):
        for key in keys:
            value = nested.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
    return ""


def _now_minus_minutes_rfc3339(minutes: int) -> str:
    delta = max(1, int(minutes or 1))
    ts = datetime.now(timezone.utc) - timedelta(minutes=delta)
    return ts.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fetch_events_after_cursor(
    *,
    db_path: Path,
    cursor: int,
    limit: int,
) -> list[dict[str, Any]]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, ts, event_type, entity_type, entity_id, payload_json
            FROM events
            WHERE id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (max(0, int(cursor)), max(1, min(int(limit or 200), 1000))),
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


def _fetch_event_by_id(*, db_path: Path, event_id: int) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute(
            """
            SELECT id, ts, event_type, entity_type, entity_id, payload_json
            FROM events
            WHERE id=?
            LIMIT 1
            """,
            (int(event_id),),
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        con.close()


def _fetch_latest_tenant_event(
    *, db_path: Path, tenant_id: str
) -> dict[str, Any] | None:
    rows = _fetch_events_after_cursor(db_path=db_path, cursor=0, limit=500)
    tenant = str(tenant_id or "").strip()
    for row in reversed(rows):
        payload = _safe_json_loads(str(row.get("payload_json") or "{}"))
        if str(payload.get("tenant_id") or "").strip() == tenant:
            return row
    return None


def _rule_eventlog_triggers(rule: dict[str, Any]) -> list[dict[str, Any]]:
    triggers = rule.get("triggers") or []
    out: list[dict[str, Any]] = []
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        trigger_type = str(trigger.get("type") or "").strip().lower()
        if trigger_type != EVENTLOG_SOURCE:
            continue
        cfg = trigger.get("config")
        out.append(cfg if isinstance(cfg, dict) else {})
    return out


def _rule_cron_triggers(rule: dict[str, Any]) -> list[dict[str, Any]]:
    triggers = rule.get("triggers") or []
    out: list[dict[str, Any]] = []
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        trigger_type = str(trigger.get("type") or "").strip().lower()
        if trigger_type != CRON_SOURCE:
            continue
        cfg = trigger.get("config")
        out.append(cfg if isinstance(cfg, dict) else {})
    return out


def _trigger_matches_event(trigger_cfg: dict[str, Any], event_type: str) -> bool:
    allowed = trigger_cfg.get("allowed_event_types")
    if not isinstance(allowed, list) or not allowed:
        return False
    allowed_set = {str(item).strip() for item in allowed if str(item).strip()}
    return str(event_type or "").strip() in allowed_set


def _cron_expression(trigger_cfg: Mapping[str, Any]) -> str:
    return str(trigger_cfg.get("cron") or trigger_cfg.get("expression") or "").strip()


def _trigger_matches_cron(trigger_cfg: Mapping[str, Any], dt: datetime) -> bool:
    expr = _cron_expression(trigger_cfg)
    if not expr:
        return False
    try:
        return bool(cron_match(expr, dt))
    except ValueError:
        return False


def _load_eventlog_rules(tenant_id: str, db_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    summaries = list_rules(tenant_id=tenant_id, db_path=db_path)
    for summary in summaries:
        if not bool(summary.get("is_enabled")):
            continue
        rid = str(summary.get("id") or "").strip()
        if not rid:
            continue
        full = get_rule(tenant_id=tenant_id, rule_id=rid, db_path=db_path)
        if not full:
            continue
        if _rule_eventlog_triggers(full):
            out.append(full)
    return out


def _load_cron_rules(tenant_id: str, db_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    summaries = list_rules(tenant_id=tenant_id, db_path=db_path)
    for summary in summaries:
        if not bool(summary.get("is_enabled")):
            continue
        rid = str(summary.get("id") or "").strip()
        if not rid:
            continue
        full = get_rule(tenant_id=tenant_id, rule_id=rid, db_path=db_path)
        if not full:
            continue
        if _rule_cron_triggers(full):
            out.append(full)
    return out


def _process_rule_for_event(
    *,
    tenant_id: str,
    rule: dict[str, Any],
    event_row: dict[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    rule_id = str(rule.get("id") or "").strip()
    event_id = int(event_row.get("id") or 0)
    event_type = str(event_row.get("event_type") or "").strip()
    if not rule_id or event_id <= 0 or not event_type:
        return {"ok": False, "reason": "validation_error"}

    matched = False
    for trigger_cfg in _rule_eventlog_triggers(rule):
        if _trigger_matches_event(trigger_cfg, event_type):
            matched = True
            break
    if not matched:
        return {"ok": True, "matched": False}

    max_execs = int(rule.get("max_executions_per_minute") or 10)
    recent_count = count_execution_logs_since(
        tenant_id=tenant_id,
        rule_id=rule_id,
        since_rfc3339=_now_minus_minutes_rfc3339(1),
        db_path=db_path,
    )
    if recent_count >= max_execs:
        trigger_ref = f"{EVENTLOG_SOURCE}:{event_id}"
        appended = append_execution_log(
            tenant_id=tenant_id,
            rule_id=rule_id,
            trigger_type=EVENTLOG_SOURCE,
            trigger_ref=trigger_ref,
            status="rate_limited",
            output_redacted=f"rate_limited:max={max_execs}",
            db_path=db_path,
        )
        return {
            "ok": True,
            "matched": True,
            "duplicate": bool(appended.get("duplicate")),
            "rate_limited": True,
        }

    trigger_ref = f"{EVENTLOG_SOURCE}:{event_id}"
    appended = append_execution_log(
        tenant_id=tenant_id,
        rule_id=rule_id,
        trigger_type=EVENTLOG_SOURCE,
        trigger_ref=trigger_ref,
        status="started",
        output_redacted=f"event:{event_type}",
        db_path=db_path,
    )
    if bool(appended.get("duplicate")):
        return {"ok": True, "matched": True, "duplicate": True}

    log_id = str(appended.get("log_id") or "").strip()
    if not log_id:
        return {"ok": False, "reason": "execution_log_append_failed"}

    context = _build_context(
        tenant_id=tenant_id, event_row=event_row, trigger_ref=trigger_ref
    )
    if not _rule_conditions_pass(rule, context):
        update_execution_log(
            tenant_id=tenant_id,
            log_id=log_id,
            status="skipped",
            output_redacted="condition_false",
            db_path=db_path,
        )
        return {"ok": True, "matched": True, "duplicate": False}

    actions = [a for a in (rule.get("actions") or []) if isinstance(a, Mapping)]
    action_payloads = [
        {"action_type": str(a.get("type") or "").strip(), **(a.get("config") or {})}
        for a in actions
    ]
    action_result = run_rule_actions(
        tenant_id=tenant_id,
        rule_id=rule_id,
        actions=action_payloads,
        context=context,
        db_path=db_path,
    )
    if not bool(action_result.get("ok")):
        update_execution_log(
            tenant_id=tenant_id,
            log_id=log_id,
            status="failed",
            error_redacted="error_permanent:action_execution_failed",
            output_redacted=str(action_result.get("summary_redacted") or ""),
            db_path=db_path,
        )
        return {"ok": False, "reason": "error_permanent:action_execution_failed"}

    status = "pending" if int(action_result.get("pending") or 0) > 0 else "ok"
    reason = "action_pending" if status == "pending" else "ok"

    update_execution_log(
        tenant_id=tenant_id,
        log_id=log_id,
        status=status,
        output_redacted=f"{reason}:{str(action_result.get('summary_redacted') or '')}",
        db_path=db_path,
    )
    return {"ok": True, "matched": True, "duplicate": False}


def _build_context(
    *,
    tenant_id: str,
    event_row: Mapping[str, Any],
    trigger_ref: str,
) -> dict[str, str]:
    payload = _safe_json_loads(str(event_row.get("payload_json") or "{}"))
    context = {
        "event_id": str(event_row.get("id") or ""),
        "event_type": str(event_row.get("event_type") or ""),
        "entity_type": str(event_row.get("entity_type") or ""),
        "entity_id": str(event_row.get("entity_id") or ""),
        "tenant_id": tenant_id,
        "timestamp": str(event_row.get("ts") or ""),
        "trigger_ref": str(trigger_ref or ""),
        "source": EVENTLOG_SOURCE,
        "from_domain": _payload_value(payload, "from_domain"),
        "thread_id": _payload_value(payload, "thread_id"),
        "account_id": _payload_value(payload, "account_id"),
        "lead_id": _payload_value(payload, "lead_id"),
        "case_id": _payload_value(payload, "case_id"),
        "source_kind": _payload_value(payload, "source_kind"),
        "source_action": _payload_value(payload, "action", "detail_code"),
        "task_status": _payload_value(payload, "task_status", "status"),
        "intent": _payload_value(payload, "intent"),
    }
    return context


def _rule_conditions_pass(rule: dict[str, Any], context: Mapping[str, Any]) -> bool:
    conditions = rule.get("conditions") or []
    if not isinstance(conditions, list):
        return False
    if not conditions:
        return True
    for condition in conditions:
        if not isinstance(condition, Mapping):
            return False
        cfg = condition.get("config")
        if not isinstance(cfg, Mapping):
            return False
        if not evaluate_conditions(
            cfg, context, allowed_fields=sorted(CONTEXT_ALLOWLIST)
        ):
            return False
    return True


def _build_cron_context(
    *,
    tenant_id: str,
    trigger_ref: str,
    cron_expression: str,
    now_dt: datetime,
) -> dict[str, str]:
    current = now_dt.replace(second=0, microsecond=0)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return {
        "event_id": "",
        "event_type": "cron.tick",
        "entity_type": "",
        "entity_id": "",
        "tenant_id": tenant_id,
        "timestamp": current.isoformat().replace("+00:00", "Z"),
        "trigger_ref": trigger_ref,
        "source": CRON_SOURCE,
        "from_domain": "",
        "cron_expression": cron_expression,
        "scheduled_minute": cron_minute_ref(current),
    }


def _process_rule_for_cron(
    *,
    tenant_id: str,
    rule: dict[str, Any],
    trigger_cfg: dict[str, Any],
    now_dt: datetime,
    db_path: Path,
) -> dict[str, Any]:
    rule_id = str(rule.get("id") or "").strip()
    cron_expr = _cron_expression(trigger_cfg)
    if not rule_id or not cron_expr:
        return {"ok": False, "reason": "validation_error"}
    if not _trigger_matches_cron(trigger_cfg, now_dt):
        return {"ok": True, "matched": False}

    trigger_ref = f"{CRON_SOURCE}:{rule_id}:{cron_minute_ref(now_dt)}"
    max_execs = int(rule.get("max_executions_per_minute") or 10)
    recent_count = count_execution_logs_since(
        tenant_id=tenant_id,
        rule_id=rule_id,
        since_rfc3339=_now_minus_minutes_rfc3339(1),
        db_path=db_path,
    )
    if recent_count >= max_execs:
        appended = append_execution_log(
            tenant_id=tenant_id,
            rule_id=rule_id,
            trigger_type=CRON_SOURCE,
            trigger_ref=trigger_ref,
            status="rate_limited",
            output_redacted=f"rate_limited:max={max_execs}",
            db_path=db_path,
        )
        return {
            "ok": True,
            "matched": True,
            "duplicate": bool(appended.get("duplicate")),
            "rate_limited": True,
        }

    appended = append_execution_log(
        tenant_id=tenant_id,
        rule_id=rule_id,
        trigger_type=CRON_SOURCE,
        trigger_ref=trigger_ref,
        status="started",
        output_redacted="cron_tick",
        db_path=db_path,
    )
    if bool(appended.get("duplicate")):
        return {"ok": True, "matched": True, "duplicate": True}

    log_id = str(appended.get("log_id") or "").strip()
    if not log_id:
        return {"ok": False, "reason": "execution_log_append_failed"}

    context = _build_cron_context(
        tenant_id=tenant_id,
        trigger_ref=trigger_ref,
        cron_expression=cron_expr,
        now_dt=now_dt,
    )
    if not _rule_conditions_pass(rule, context):
        update_execution_log(
            tenant_id=tenant_id,
            log_id=log_id,
            status="skipped",
            output_redacted="condition_false",
            db_path=db_path,
        )
        return {"ok": True, "matched": True, "duplicate": False}

    actions = [a for a in (rule.get("actions") or []) if isinstance(a, Mapping)]
    action_payloads = [
        {"action_type": str(a.get("type") or "").strip(), **(a.get("config") or {})}
        for a in actions
    ]
    action_result = run_rule_actions(
        tenant_id=tenant_id,
        rule_id=rule_id,
        actions=action_payloads,
        context=context,
        db_path=db_path,
    )
    if not bool(action_result.get("ok")):
        update_execution_log(
            tenant_id=tenant_id,
            log_id=log_id,
            status="failed",
            error_redacted="error_permanent:action_execution_failed",
            output_redacted=str(action_result.get("summary_redacted") or ""),
            db_path=db_path,
        )
        return {"ok": False, "reason": "error_permanent:action_execution_failed"}

    status = "pending" if int(action_result.get("pending") or 0) > 0 else "ok"
    reason = "action_pending" if status == "pending" else "ok"
    update_execution_log(
        tenant_id=tenant_id,
        log_id=log_id,
        status=status,
        output_redacted=f"{reason}:{str(action_result.get('summary_redacted') or '')}",
        db_path=db_path,
    )
    return {"ok": True, "matched": True, "duplicate": False}


def process_events_for_tenant(
    tenant_id: str,
    *,
    db_path: Path | str | None = None,
    limit: int = 200,
    source: str = EVENTLOG_SOURCE,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("validation_error")

    src = str(source or "").strip().lower()
    if src != EVENTLOG_SOURCE:
        raise ValueError("validation_error")

    resolved_db = _resolve_db_path(db_path)
    rules = _load_eventlog_rules(tenant, resolved_db)
    cursor_raw = get_state_cursor(tenant_id=tenant, source=src, db_path=resolved_db)
    cursor = int(cursor_raw) if cursor_raw.isdigit() else 0
    last_cursor = cursor

    events = _fetch_events_after_cursor(db_path=resolved_db, cursor=cursor, limit=limit)
    processed = 0
    matched = 0
    duplicates = 0

    for event_row in events:
        event_id = int(event_row.get("id") or 0)
        if event_id <= 0:
            continue
        payload = _safe_json_loads(str(event_row.get("payload_json") or "{}"))
        payload_tenant = str(payload.get("tenant_id") or "").strip()
        if payload_tenant != tenant:
            last_cursor = event_id
            continue

        for rule in rules:
            outcome: dict[str, Any] | None = None
            for attempt in (0, 1):
                try:
                    outcome = _process_rule_for_event(
                        tenant_id=tenant,
                        rule=rule,
                        event_row=event_row,
                        db_path=resolved_db,
                    )
                    break
                except sqlite3.OperationalError:
                    if attempt == 0:
                        time.sleep(0.1)
                        continue
                    return {
                        "ok": False,
                        "reason": "error_transient:rule_processing_failed",
                        "processed": processed,
                        "matched": matched,
                        "duplicates": duplicates,
                        "cursor": str(last_cursor),
                    }
                except Exception:
                    return {
                        "ok": False,
                        "reason": "error_permanent:rule_processing_failed",
                        "processed": processed,
                        "matched": matched,
                        "duplicates": duplicates,
                        "cursor": str(last_cursor),
                    }
            if outcome is None:
                return {
                    "ok": False,
                    "reason": "error_transient:rule_processing_failed",
                    "processed": processed,
                    "matched": matched,
                    "duplicates": duplicates,
                    "cursor": str(last_cursor),
                }
            if not bool(outcome.get("ok")):
                return {
                    "ok": False,
                    "reason": str(outcome.get("reason") or "rule_processing_failed"),
                    "processed": processed,
                    "matched": matched,
                    "duplicates": duplicates,
                    "cursor": str(last_cursor),
                }
            if bool(outcome.get("matched")):
                matched += 1
                if bool(outcome.get("duplicate")):
                    duplicates += 1
        processed += 1
        last_cursor = event_id

    if last_cursor > cursor:
        upsert_state_cursor(
            tenant_id=tenant,
            source=src,
            cursor=str(last_cursor),
            db_path=resolved_db,
        )

    return {
        "ok": True,
        "reason": "ok",
        "processed": processed,
        "matched": matched,
        "duplicates": duplicates,
        "cursor": str(last_cursor),
    }


def process_cron_for_tenant(
    tenant_id: str,
    *,
    db_path: Path | str | None = None,
    now_dt: datetime | None = None,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise ValueError("validation_error")
    resolved_db = _resolve_db_path(db_path)
    current = now_dt or datetime.now(timezone.utc)
    rules = _load_cron_rules(tenant, resolved_db)
    processed = 0
    matched = 0
    duplicates = 0
    for rule in rules:
        for trigger_cfg in _rule_cron_triggers(rule):
            outcome = _process_rule_for_cron(
                tenant_id=tenant,
                rule=rule,
                trigger_cfg=trigger_cfg,
                now_dt=current,
                db_path=resolved_db,
            )
            if not bool(outcome.get("ok")):
                return {
                    "ok": False,
                    "reason": str(outcome.get("reason") or "rule_processing_failed"),
                    "processed": processed,
                    "matched": matched,
                    "duplicates": duplicates,
                }
            processed += 1
            if bool(outcome.get("matched")):
                matched += 1
                if bool(outcome.get("duplicate")):
                    duplicates += 1
    return {
        "ok": True,
        "reason": "ok",
        "processed": processed,
        "matched": matched,
        "duplicates": duplicates,
    }


def _list_tenants_with_cron_rules(db_path: Path) -> list[str]:
    con = _connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT DISTINCT r.tenant_id
            FROM automation_builder_rules r
            JOIN automation_builder_triggers t
              ON t.tenant_id=r.tenant_id AND t.rule_id=r.id
            WHERE r.is_enabled=1
              AND LOWER(TRIM(t.trigger_type))=?
            ORDER BY r.tenant_id ASC
            """,
            (CRON_SOURCE,),
        ).fetchall()
        return [
            str(row["tenant_id"] or "").strip()
            for row in rows
            if str(row["tenant_id"] or "").strip()
        ]
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


class CronChecker(threading.Thread):
    def __init__(
        self,
        *,
        db_path: Path,
        interval_seconds: int = 60,
    ) -> None:
        super().__init__(name="automation-cron-checker", daemon=True)
        self._db_path = db_path
        self._interval_seconds = max(10, int(interval_seconds or 60))
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:  # pragma: no cover - thread behavior
        while not self._stop_event.is_set():
            tick = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            for tenant_id in _list_tenants_with_cron_rules(self._db_path):
                try:
                    process_cron_for_tenant(
                        tenant_id,
                        db_path=self._db_path,
                        now_dt=tick,
                    )
                except Exception:
                    continue
            self._stop_event.wait(self._interval_seconds)


def start_cron_checker(
    *,
    db_path: Path | str | None = None,
    interval_seconds: int = 60,
) -> CronChecker:
    global _CRON_CHECKER
    resolved = _resolve_db_path(db_path)
    with _CRON_CHECKER_LOCK:
        if _CRON_CHECKER is not None and _CRON_CHECKER.is_alive():
            return _CRON_CHECKER
        checker = CronChecker(db_path=resolved, interval_seconds=interval_seconds)
        checker.start()
        _CRON_CHECKER = checker
        return checker


def stop_cron_checker() -> None:
    global _CRON_CHECKER
    with _CRON_CHECKER_LOCK:
        if _CRON_CHECKER is None:
            return
        _CRON_CHECKER.stop()
        _CRON_CHECKER = None


def simulate_rule_for_tenant(
    tenant_id: str,
    rule_id: str,
    *,
    db_path: Path | str | None = None,
    event_id: int | None = None,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip()
    rid = str(rule_id or "").strip()
    if not tenant or not rid:
        raise ValueError("validation_error")

    resolved_db = _resolve_db_path(db_path)
    rule = get_rule(tenant_id=tenant, rule_id=rid, db_path=resolved_db)
    if not rule:
        return {"ok": False, "reason": "not_found"}

    row = (
        _fetch_event_by_id(db_path=resolved_db, event_id=int(event_id))
        if event_id is not None
        else _fetch_latest_tenant_event(db_path=resolved_db, tenant_id=tenant)
    )
    if not row:
        return {"ok": False, "reason": "event_not_found"}

    payload = _safe_json_loads(str(row.get("payload_json") or "{}"))
    if str(payload.get("tenant_id") or "").strip() != tenant:
        return {"ok": False, "reason": "event_not_found"}

    ev_type = str(row.get("event_type") or "").strip()
    matched = any(
        _trigger_matches_event(cfg, ev_type) for cfg in _rule_eventlog_triggers(rule)
    )
    trigger_ref = f"simulation:eventlog:{int(row.get('id') or 0)}"
    context = _build_context(tenant_id=tenant, event_row=row, trigger_ref=trigger_ref)
    cond_ok = matched and _rule_conditions_pass(rule, context)
    actions_payload = [
        {"action_type": str(a.get("type") or "").strip(), **(a.get("config") or {})}
        for a in (rule.get("actions") or [])
        if isinstance(a, Mapping)
    ]
    action_result = (
        run_rule_actions(
            tenant_id=tenant,
            rule_id=rid,
            actions=actions_payload,
            context=context,
            db_path=resolved_db,
            dry_run=True,
        )
        if cond_ok
        else {
            "ok": True,
            "executed": 0,
            "pending": 0,
            "failed": 0,
            "details": [],
            "summary_redacted": '{"simulated":true}',
        }
    )
    if not matched:
        status = "skipped"
        reason = "trigger_not_matched"
    elif not cond_ok:
        status = "skipped"
        reason = "condition_false"
    elif not bool(action_result.get("ok")):
        status = "failed"
        reason = "error_permanent:simulation_action_failed"
    elif int(action_result.get("pending") or 0) > 0:
        status = "pending"
        reason = "action_pending"
    else:
        status = "ok"
        reason = "ok"

    append_execution_log(
        tenant_id=tenant,
        rule_id=rid,
        trigger_type="simulation",
        trigger_ref=f"{trigger_ref}:{int(time.time())}",
        status=status,
        error_redacted="" if status != "failed" else reason,
        output_redacted=reason,
        db_path=resolved_db,
    )
    return {
        "ok": status != "failed",
        "reason": reason,
        "status": status,
        "matched": matched,
        "condition_passed": cond_ok,
        "event_id": int(row.get("id") or 0),
        "event_type": ev_type,
        "result": action_result,
    }
