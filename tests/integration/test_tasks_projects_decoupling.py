from __future__ import annotations

import sqlite3

from app import create_app
from app.modules.projects.logic import ProjectManager


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    return app, app.test_client()


def _ensure_membership(app, *, tenant_id: str, username: str = "dev", role: str = "DEV") -> None:
    con = sqlite3.connect(app.config["AUTH_DB"])
    try:
        con.execute(
            """
            INSERT OR REPLACE INTO memberships(tenant_id, username, role, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (tenant_id, username, role),
        )
        con.commit()
    finally:
        con.close()


def test_team_tasks_store_project_links_separate_from_task_domain(tmp_path, monkeypatch):
    app, _client = _bootstrap(tmp_path, monkeypatch)
    tenant_id = "KUKANILEA"
    _ensure_membership(app, tenant_id=tenant_id)
    pm = ProjectManager(app.extensions["auth_db"])

    task_id = pm.create_team_task(
        tenant_id=tenant_id,
        actor="dev",
        actor_role="DEV",
        title="Domain ownership remains in task module",
        due_at="2030-01-10",
        assigned_to="dev",
        project_id="project-alpha",
        project_board_id="board-kanban-alpha",
        project_card_id="card-42",
    )

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT id, board_id, project_id, project_board_id, project_card_id FROM team_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["project_id"] == "project-alpha"
    assert row["project_board_id"] == "board-kanban-alpha"
    assert row["project_card_id"] == "card-42"
    # Legacy board_id stays populated for backward compatibility only.
    assert row["board_id"] == "board-kanban-alpha"


def test_execute_task_command_maps_legacy_board_id_to_project_board_link(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)
    tenant_id = "KUKANILEA"
    _ensure_membership(app, tenant_id=tenant_id)

    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = tenant_id

    with app.test_request_context("/"):
        pm = ProjectManager(app.extensions["auth_db"])
        # mirror session identity in this request context
        from flask import session

        session["user"] = "dev"
        session["role"] = "DEV"
        session["tenant_id"] = tenant_id

        result = pm.execute_task_command(
            {
                "action": "create",
                "title": "Legacy API payload",
                "assigned_to": "dev",
                "board_id": "legacy-board-1",
            }
        )

    assert result["ok"] is True

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT project_board_id FROM team_tasks WHERE id = ?",
            (result["task_id"],),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["project_board_id"] == "legacy-board-1"
