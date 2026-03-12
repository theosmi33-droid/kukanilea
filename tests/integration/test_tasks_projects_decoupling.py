from __future__ import annotations

import sqlite3

import pytest

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


def test_create_task_defaults_project_links_without_cross_domain_ids(tmp_path, monkeypatch):
    app, _client = _bootstrap(tmp_path, monkeypatch)
    tenant_id = "KUKANILEA"
    _ensure_membership(app, tenant_id=tenant_id)

    with app.test_request_context("/"):
        from flask import session

        session["user"] = "dev"
        session["role"] = "DEV"
        session["tenant_id"] = tenant_id

        pm = ProjectManager(app.extensions["auth_db"])
        task_id = pm.create_task(
            board_id="legacy-board-only",
            title="Legacy board without explicit project",
            content="Backwards compatible write path",
            assigned="dev",
        )

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT board_id, project_id, project_board_id, project_card_id
            FROM team_tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["board_id"] == "legacy-board-only"
    assert row["project_board_id"] == "legacy-board-only"
    assert row["project_id"] is None
    assert row["project_card_id"] is None


def test_execute_task_command_prefers_project_board_id_over_legacy_alias(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)
    tenant_id = "KUKANILEA"
    _ensure_membership(app, tenant_id=tenant_id)

    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = tenant_id

    with app.test_request_context("/"):
        from flask import session

        session["user"] = "dev"
        session["role"] = "DEV"
        session["tenant_id"] = tenant_id

        pm = ProjectManager(app.extensions["auth_db"])
        result = pm.execute_task_command(
            {
                "action": "create",
                "title": "Prefer explicit project board",
                "assigned_to": "dev",
                "board_id": "legacy-board-ignored",
                "project_board_id": "project-board-explicit",
                "project_id": "project-zeta",
                "project_card_id": "card-zeta-1",
            }
        )

    assert result["ok"] is True

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT board_id, project_id, project_board_id, project_card_id
            FROM team_tasks
            WHERE id = ?
            """,
            (result["task_id"],),
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    # Legacy alias remains synchronized with explicit board link.
    assert row["board_id"] == "project-board-explicit"
    assert row["project_board_id"] == "project-board-explicit"
    assert row["project_id"] == "project-zeta"
    assert row["project_card_id"] == "card-zeta-1"


def test_update_task_column_legacy_fallback_blocks_cross_tenant_move(tmp_path, monkeypatch):
    app, _client = _bootstrap(tmp_path, monkeypatch)
    pm = ProjectManager(app.extensions["auth_db"])

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        con.execute(
            "INSERT OR REPLACE INTO tenants(tenant_id, display_name, created_at) VALUES (?, ?, datetime('now'))",
            ("TENANT_A", "Tenant A"),
        )
        con.execute(
            "INSERT OR REPLACE INTO tenants(tenant_id, display_name, created_at) VALUES (?, ?, datetime('now'))",
            ("TENANT_B", "Tenant B"),
        )
        con.execute(
            "INSERT OR REPLACE INTO projects(id, tenant_id, name, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("project-a", "TENANT_A", "Project A"),
        )
        con.execute(
            "INSERT OR REPLACE INTO boards(id, project_id, name, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("board-a", "project-a", "Board A"),
        )
        con.execute(
            """
            INSERT OR REPLACE INTO tasks(
                id, board_id, column_name, title, content, assigned_user,
                due_date, priority, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("legacy-task-1", "board-a", "To Do", "Legacy Task", "", "", None, None),
        )
        con.commit()
    finally:
        con.close()

    with app.test_request_context("/"):
        from flask import session

        session["user"] = "bob"
        session["role"] = "DEV"
        session["tenant_id"] = "TENANT_B"
        result = pm.update_task_column("legacy-task-1", "Done")

    assert result["ok"] is False
    assert result["error"] == "task_not_found_or_forbidden"

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT column_name FROM tasks WHERE id = ?", ("legacy-task-1",)).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["column_name"] == "To Do"


def test_execute_task_command_blocks_cross_tenant_for_admin_role(tmp_path, monkeypatch):
    app, _client = _bootstrap(tmp_path, monkeypatch)
    pm = ProjectManager(app.extensions["auth_db"])

    _ensure_membership(app, tenant_id="TENANT_B", username="bob", role="ADMIN")

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        con.execute(
            """
            INSERT OR REPLACE INTO team_tasks(
                id, tenant_id, board_id, project_id, project_board_id, project_card_id,
                title, description, priority, due_at, status, created_by, assigned_to,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "team-task-admin-cross-tenant",
                "TENANT_A",
                "board-a",
                "project-a",
                "board-a",
                "",
                "Cross Tenant Team Task",
                "",
                "MEDIUM",
                None,
                "OPEN",
                "alice",
                "alice",
            ),
        )
        con.commit()
    finally:
        con.close()

    with app.test_request_context("/"):
        from flask import session

        session["user"] = "bob"
        session["role"] = "ADMIN"
        session["tenant_id"] = "TENANT_B"

        with pytest.raises(PermissionError, match="cross_tenant_forbidden"):
            pm.execute_task_command({"action": "start", "task_id": "team-task-admin-cross-tenant"})

def test_update_task_column_team_tasks_path_blocks_cross_tenant_move(tmp_path, monkeypatch):
    app, _client = _bootstrap(tmp_path, monkeypatch)
    pm = ProjectManager(app.extensions["auth_db"])

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        con.execute(
            """
            INSERT OR REPLACE INTO team_tasks(
                id, tenant_id, board_id, project_id, project_board_id, project_card_id,
                title, description, priority, due_at, status, created_by, assigned_to,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "team-task-1",
                "TENANT_A",
                "board-a",
                "project-a",
                "board-a",
                "",
                "Cross Tenant Team Task",
                "",
                "MEDIUM",
                None,
                "OPEN",
                "alice",
                "alice",
            ),
        )
        con.commit()
    finally:
        con.close()

    with app.test_request_context("/"):
        from flask import session

        session["user"] = "bob"
        session["role"] = "DEV"
        session["tenant_id"] = "TENANT_B"
        result = pm.update_task_column("team-task-1", "Done")

    assert result["ok"] is False
    assert result["error"] == "task_not_found_or_forbidden"

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT status FROM team_tasks WHERE id = ?", ("team-task-1",)).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["status"] == "OPEN"


def test_api_task_move_returns_403_for_cross_tenant_legacy_task(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        con.execute(
            "INSERT OR REPLACE INTO tenants(tenant_id, display_name, created_at) VALUES (?, ?, datetime('now'))",
            ("TENANT_A", "Tenant A"),
        )
        con.execute(
            "INSERT OR REPLACE INTO tenants(tenant_id, display_name, created_at) VALUES (?, ?, datetime('now'))",
            ("TENANT_B", "Tenant B"),
        )
        con.execute(
            "INSERT OR REPLACE INTO projects(id, tenant_id, name, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("project-a", "TENANT_A", "Project A"),
        )
        con.execute(
            "INSERT OR REPLACE INTO boards(id, project_id, name, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("board-a", "project-a", "Board A"),
        )
        con.execute(
            """
            INSERT OR REPLACE INTO tasks(
                id, board_id, column_name, title, content, assigned_user,
                due_date, priority, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("legacy-task-2", "board-a", "To Do", "Legacy Task", "", "", None, None),
        )
        con.commit()
    finally:
        con.close()

    with client.session_transaction() as sess:
        sess["user"] = "bob"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_B"
        sess["csrf_token"] = "csrf-test"

    response = client.post(
        "/api/tasks/legacy-task-2/move",
        json={"column": "Done"},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"] == "task_not_found_or_forbidden"

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT column_name FROM tasks WHERE id = ?", ("legacy-task-2",)).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["column_name"] == "To Do"


def test_api_task_move_requires_operator_role(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)

    with client.session_transaction() as sess:
        sess["user"] = "readonly-user"
        sess["role"] = "READONLY"
        sess["tenant_id"] = "TENANT_A"
        sess["csrf_token"] = "csrf-test"

    response = client.post(
        "/api/tasks/any-task/move",
        json={"column": "Done"},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["error"]["code"] == "forbidden"


def test_api_task_move_allows_same_tenant_legacy_task_update(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        con.execute(
            "INSERT OR REPLACE INTO tenants(tenant_id, display_name, created_at) VALUES (?, ?, datetime('now'))",
            ("TENANT_A", "Tenant A"),
        )
        con.execute(
            "INSERT OR REPLACE INTO projects(id, tenant_id, name, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("project-a", "TENANT_A", "Project A"),
        )
        con.execute(
            "INSERT OR REPLACE INTO boards(id, project_id, name, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("board-a", "project-a", "Board A"),
        )
        con.execute(
            """
            INSERT OR REPLACE INTO tasks(
                id, board_id, column_name, title, content, assigned_user,
                due_date, priority, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            ("legacy-task-3", "board-a", "To Do", "Legacy Task", "", "", None, None),
        )
        con.commit()
    finally:
        con.close()

    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
        sess["csrf_token"] = "csrf-test"

    response = client.post(
        "/api/tasks/legacy-task-3/move",
        json={"column": "Done"},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT column_name FROM tasks WHERE id = ?", ("legacy-task-3",)).fetchone()
    finally:
        con.close()

    assert row is not None
    assert row["column_name"] == "Done"


def test_api_task_move_returns_403_for_unknown_task(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)

    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
        sess["csrf_token"] = "csrf-test"

    response = client.post(
        "/api/tasks/does-not-exist/move",
        json={"column": "Done"},
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body["ok"] is False
    assert body["error"] == "task_not_found_or_forbidden"
