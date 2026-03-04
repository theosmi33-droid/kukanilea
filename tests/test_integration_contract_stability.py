from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from app import web


class _AuthDBStub:
    def __init__(self, db_path: Path) -> None:
        self._path = db_path

    def _db(self):
        con = sqlite3.connect(str(self._path))
        con.row_factory = sqlite3.Row
        return con


@pytest.fixture()
def client(tmp_path: Path):
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parents[1] / "app" / "templates"),
    )
    app.secret_key = "test-secret"

    db_path = tmp_path / "auth.sqlite3"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE projects(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL)")
    con.execute(
        "CREATE TABLE boards(id TEXT PRIMARY KEY, project_id TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE team_tasks(id TEXT PRIMARY KEY, board_id TEXT NOT NULL)"
    )
    con.execute("INSERT INTO projects(id, tenant_id) VALUES ('p1', 'TENANT')")
    con.execute("INSERT INTO boards(id, project_id) VALUES ('b1', 'p1')")
    con.execute("INSERT INTO team_tasks(id, board_id) VALUES ('t1', 'b1')")
    con.commit()
    con.close()

    app.extensions["auth_db"] = _AuthDBStub(db_path)
    app.register_blueprint(web.bp)

    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "TENANT"

    return test_client


def test_tasks_summary_endpoint_uses_ids_contract(client, monkeypatch):
    monkeypatch.setattr(
        web,
        "task_list",
        lambda tenant, status, limit: [
            {"id": 1, "status": "OPEN"},
            {"id": 2, "status": "DONE"},
        ],
    )
    response = client.get("/api/tasks/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["total"] == 2
    assert data["summary"]["by_status"]["OPEN"] == 1


def test_tasks_route_renders(client):
    response = client.get("/tasks", headers={"HX-Request": "true"})
    assert response.status_code == 200


def test_projects_summary_endpoint(client):
    response = client.get("/api/projects/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"] == {"project_count": 1, "board_count": 1, "task_count": 1}


def test_projects_route_renders(client):
    response = client.get("/projects", headers={"HX-Request": "true"})
    assert response.status_code == 200


def test_time_summary_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        web,
        "time_entry_list",
        lambda **kwargs: [
            {"id": 10, "duration_seconds": 120},
            {"id": 11, "duration_seconds": 180},
        ],
    )
    response = client.get("/api/time/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["entries"] == 2
    assert data["summary"]["total_seconds"] == 300


def test_time_route_renders(client):
    response = client.get("/time", headers={"HX-Request": "true"})
    assert response.status_code == 200


def test_calendar_summary_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        web,
        "calendar_reminders_due",
        lambda tenant: [{"id": "c-1"}, {"id": "c-2"}],
    )
    response = client.get("/api/calendar/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["summary"]["reminder_count"] == 2
    assert data["summary"]["reminder_ids"] == ["c-1", "c-2"]


def test_calendar_route_renders(client):
    response = client.get("/calendar", headers={"HX-Request": "true"})
    assert response.status_code == 200
