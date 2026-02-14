from __future__ import annotations

import io
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app import create_app
from app.knowledge.core import knowledge_policy_update


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _client(tmp_path: Path):
    _init_core(tmp_path)
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        READ_ONLY=False,
        KNOWLEDGE_ICS_MAX_BYTES=512,
    )
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "TENANT_A"
    with app.app_context():
        knowledge_policy_update(
            "TENANT_A",
            actor_user_id="dev",
            allow_customer_pii=True,
            allow_calendar=True,
        )
    return client


def test_ics_oversize_upload_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    data = b"BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:X\nEND:VEVENT\nEND:VCALENDAR\n" + (
        b"x" * 4096
    )
    resp = client.post(
        "/knowledge/ics/upload",
        data={"file": (io.BytesIO(data), "big.ics")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413
