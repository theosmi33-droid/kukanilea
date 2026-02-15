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


def _client(tmp_path: Path, *, read_only: bool = False):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test", READ_ONLY=read_only)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    return client


def test_autonomy_health_page_and_actions(tmp_path: Path, monkeypatch) -> None:
    backup_root = tmp_path / "backups"
    log_root = tmp_path / "logs"
    monkeypatch.setenv("KUKANILEA_BACKUP_DIR", str(backup_root))
    monkeypatch.setenv("KUKANILEA_LOG_DIR", str(log_root))

    client = _client(tmp_path, read_only=False)
    page = client.get("/autonomy/health")
    assert page.status_code == 200
    assert b"Autonomy Health" in page.data
    assert b"OCR Jobs" in page.data

    backup_resp = client.post("/autonomy/health/backup")
    assert backup_resp.status_code in {302, 200}
    rotate_resp = client.post("/autonomy/health/rotate-logs")
    assert rotate_resp.status_code in {302, 200}
    smoke_resp = client.post("/autonomy/health/smoke-test")
    assert smoke_resp.status_code in {302, 200}


def test_autonomy_health_actions_blocked_in_read_only(tmp_path: Path) -> None:
    client = _client(tmp_path, read_only=True)
    assert client.post("/autonomy/health/backup").status_code == 403
    assert client.post("/autonomy/health/rotate-logs").status_code == 403
    assert client.post("/autonomy/health/smoke-test").status_code == 403
