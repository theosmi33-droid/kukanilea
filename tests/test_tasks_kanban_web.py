from __future__ import annotations

from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path, *, tenant: str = "TENANT_A", read_only: bool = False):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=read_only)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = tenant
    return client


def test_tasks_kanban_create_and_move_flow(tmp_path: Path) -> None:
    client = _client(tmp_path)

    create = client.post(
        "/api/tasks/create",
        json={
            "title": "Kanban Test Task",
            "task_type": "GENERAL",
            "severity": "INFO",
            "details": "sample",
        },
    )
    assert create.status_code == 200
    task_id = int(create.get_json()["task_id"])

    page = client.get("/tasks")
    assert page.status_code == 200
    assert b"Tasks Kanban" in page.data

    move = client.post(
        f"/api/tasks/{task_id}/move",
        json={"column": "in_progress"},
    )
    assert move.status_code == 200
    assert move.get_json()["status"] == "IN_PROGRESS"

    done = client.post(
        f"/api/tasks/{task_id}/move",
        json={"column": "done"},
    )
    assert done.status_code == 200
    assert done.get_json()["status"] == "RESOLVED"

    resolved = client.get("/api/tasks?status=RESOLVED")
    assert resolved.status_code == 200
    ids = {int(item.get("id") or 0) for item in resolved.get_json()["tasks"]}
    assert task_id in ids


def test_tasks_read_only_blocks_mutations(tmp_path: Path) -> None:
    client = _client(tmp_path, read_only=True)
    create = client.post("/api/tasks/create", json={"title": "Blocked Task"})
    assert create.status_code == 403
    payload = create.get_json()
    assert payload["error"]["code"] == "read_only"


def test_tasks_tenant_isolation_on_move(tmp_path: Path) -> None:
    _init_core(tmp_path)
    task_id = core.task_create(
        tenant="TENANT_A",
        severity="INFO",
        task_type="GENERAL",
        title="Tenant Task",
        details="x",
        created_by="seed",
    )
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_B"

    move = client.post(
        f"/api/tasks/{int(task_id)}/move",
        json={"column": "done"},
    )
    assert move.status_code == 404
