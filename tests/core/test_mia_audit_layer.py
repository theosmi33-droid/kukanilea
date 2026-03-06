from __future__ import annotations

import sqlite3

from app.agents.executor import AgentExecutor
from app.config import Config
from app.core.agent_router import classify_intent
from app.mia_audit import (
    MIA_EVENT_ACTION_SELECTED,
    MIA_EVENT_EXTERNAL_CALL_BLOCKED,
    MIA_EVENT_INTENT_DETECTED,
    MIA_EVENT_PARAMETER_VALIDATION_FAILED,
    MIA_EVENT_ROUTE_EXECUTED,
    canonical_mia_payload,
)
from app.tools.base_tool import BaseTool
from app.tools.registry import registry


class _EchoTool(BaseTool):
    name = "tool.echo"

    def run(self, **kwargs):
        return {"ok": True, "kwargs": kwargs}


def _count_event(db_path, event_type: str) -> int:
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT COUNT(1) FROM events WHERE event_type=?", (event_type,)).fetchone()
        return int((row[0] if row else 0) or 0)
    finally:
        con.close()


def test_canonical_mia_payload_contains_required_fields_and_redacts():
    payload = canonical_mia_payload(
        tenant_id="KUKANILEA",
        user_id="alice",
        action="route.task",
        status="selected",
        risk="medium",
        meta={"access_token": "secret", "plain": "ok"},
    )
    assert payload["tenant_id"] == "KUKANILEA"
    assert payload["user_id"] == "alice"
    assert payload["action"] == "route.task"
    assert payload["status"] == "selected"
    assert payload["risk"] == "medium"
    assert payload["meta"]["access_token"] == "[REDACTED]"
    assert payload["meta"]["plain"] == "ok"


def test_router_emits_intent_and_action_events(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    Config.CORE_DB = str(db_path)

    classify_intent("zeige status", {"tenant_id": "KUKANILEA", "user_id": "alice"})

    assert _count_event(db_path, MIA_EVENT_INTENT_DETECTED) == 1
    assert _count_event(db_path, MIA_EVENT_ACTION_SELECTED) == 1


def test_executor_emits_executed_and_blocked_events(tmp_path):
    db_path = tmp_path / "core.sqlite3"
    Config.CORE_DB = str(db_path)
    registry.tools.clear()
    registry.register(_EchoTool())

    executor = AgentExecutor()
    result = executor.execute("tool.echo", {"tenant_id": "KUKANILEA", "user_id": "alice", "value": 1})
    assert result["ok"] is True
    assert _count_event(db_path, MIA_EVENT_ROUTE_EXECUTED) == 1

    try:
        executor.execute("external.crm", {"tenant_id": "KUKANILEA", "user_id": "alice"})
    except PermissionError:
        pass
    assert _count_event(db_path, MIA_EVENT_EXTERNAL_CALL_BLOCKED) == 1

    try:
        executor.execute("tool.echo", "not-a-dict")  # type: ignore[arg-type]
    except ValueError:
        pass
    assert _count_event(db_path, MIA_EVENT_PARAMETER_VALIDATION_FAILED) >= 1
