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


def test_team_task_schema_migrates_project_link_columns_for_existing_install(tmp_path, monkeypatch):
    auth_db = tmp_path / "auth.sqlite3"
    con = sqlite3.connect(auth_db)
    try:
        con.execute(
            """
            CREATE TABLE team_tasks(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              board_id TEXT,
              title TEXT NOT NULL,
              description TEXT,
              priority TEXT NOT NULL DEFAULT 'MEDIUM',
              due_at TEXT,
              status TEXT NOT NULL DEFAULT 'OPEN',
              created_by TEXT NOT NULL,
              assigned_to TEXT,
              rejection_reason TEXT,
              source_type TEXT,
              source_ref TEXT,
              parent_task_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            INSERT INTO team_tasks(
              id, tenant_id, board_id, title, description, priority, due_at, status,
              created_by, assigned_to, rejection_reason, source_type, source_ref,
              parent_task_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "legacy-1",
                "KUKANILEA",
                "legacy-board",
                "Legacy row",
                "",
                "MEDIUM",
                None,
                "OPEN",
                "dev",
                "dev",
                None,
                None,
                None,
                None,
            ),
        )
        con.commit()
    finally:
        con.close()

    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(auth_db))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    pm = ProjectManager(app.extensions["auth_db"])

    con = sqlite3.connect(app.config["AUTH_DB"])
    con.row_factory = sqlite3.Row
    try:
        columns = {
            row["name"]
            for row in con.execute("PRAGMA table_info(team_tasks)").fetchall()
        }
        row = con.execute(
            "SELECT board_id, project_id, project_board_id, project_card_id FROM team_tasks WHERE id = ?",
            ("legacy-1",),
        ).fetchone()
    finally:
        con.close()

    assert pm is not None
    assert {"project_id", "project_board_id", "project_card_id"}.issubset(columns)
    assert row is not None
    assert row["board_id"] == "legacy-board"
    assert row["project_board_id"] == "legacy-board"
    assert row["project_id"] is None
    assert row["project_card_id"] is None
