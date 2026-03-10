from __future__ import annotations

from datetime import datetime, timezone

from app.db import AuthDB
from app.modules.automation.actions import _execute_create_task


def _seed_membership(auth_db: AuthDB, *, tenant_id: str, username: str, role: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    auth_db.init()
    auth_db.upsert_tenant(tenant_id, tenant_id, now)
    auth_db.upsert_user(username, "hash", now)
    auth_db.upsert_membership(username, tenant_id, role, now)


def test_execute_create_task_uses_actor_membership_role_for_team_sync(tmp_path, monkeypatch):
    auth_db_path = tmp_path / "auth.sqlite3"
    _seed_membership(
        AuthDB(auth_db_path),
        tenant_id="TENANT",
        username="operator_1",
        role="OPERATOR",
    )
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(auth_db_path))

    captured: dict[str, str] = {}

    class FakePM:
        def __init__(self, _db):
            pass

        def create_team_task(self, **kwargs):
            captured["actor_role"] = kwargs["actor_role"]
            captured["actor"] = kwargs["actor"]
            return "team-1"

    monkeypatch.setattr("app.modules.projects.logic.ProjectManager", FakePM)
    monkeypatch.setattr("app.modules.automation.actions.core.task_create", lambda **_kwargs: 7)

    result = _execute_create_task(
        tenant_id="TENANT",
        rule_id="rule-1234",
        action_cfg={"created_by": "operator_1", "assigned_to": "other_user", "title": "T"},
        context={"trigger_ref": "evt-1", "source": "eventlog"},
    )

    assert result["status"] == "ok"
    assert captured["actor"] == "operator_1"
    assert captured["actor_role"] == "OPERATOR"


def test_execute_create_task_defaults_unknown_actor_to_readonly(tmp_path, monkeypatch):
    auth_db_path = tmp_path / "auth.sqlite3"
    AuthDB(auth_db_path).init()
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(auth_db_path))

    captured: dict[str, str] = {}

    class FakePM:
        def __init__(self, _db):
            pass

        def create_team_task(self, **kwargs):
            captured["actor_role"] = kwargs["actor_role"]
            return "team-2"

    monkeypatch.setattr("app.modules.projects.logic.ProjectManager", FakePM)
    monkeypatch.setattr("app.modules.automation.actions.core.task_create", lambda **_kwargs: 8)

    result = _execute_create_task(
        tenant_id="TENANT",
        rule_id="rule-5678",
        action_cfg={"created_by": "ghost", "title": "T"},
        context={"trigger_ref": "evt-2", "source": "eventlog"},
    )

    assert result["status"] == "ok"
    assert captured["actor_role"] == "READONLY"
