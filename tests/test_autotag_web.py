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


def test_autotag_pages_render(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/autonomy/autotag/rules").status_code == 200
    page = client.get("/autonomy/autotag/rules/new")
    assert page.status_code == 200
    assert b"Auto-Tagging" in page.data


def test_autotag_create_read_only_blocked(tmp_path: Path) -> None:
    client = _client(tmp_path, read_only=True)
    resp = client.post(
        "/autonomy/autotag/rules/create",
        data={
            "name": "Blocked",
            "priority": "0",
            "filename_glob": "*x*",
            "set_doctype_token": "invoice",
        },
    )
    assert resp.status_code == 403
