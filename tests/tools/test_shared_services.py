from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from app.tools.shared_services import build_memory_manager, get_auth_db, get_tenant_id


class _AuthDbStub:
    def __init__(self, path: str) -> None:
        self.path = path


def test_get_tenant_id_uses_context_and_default() -> None:
    app = Flask(__name__)

    with app.app_context():
        assert get_tenant_id() is None
        assert get_tenant_id(default="fallback") == "fallback"

        g.tenant_id = "tenant-a"
        assert get_tenant_id() == "tenant-a"


def test_get_auth_db_reads_flask_extension() -> None:
    app = Flask(__name__)

    with app.app_context():
        assert get_auth_db() is None

        stub = SimpleNamespace(path=Path("instance/auth.sqlite3"))
        app.extensions["auth_db"] = stub
        assert get_auth_db() is stub


def test_build_memory_manager_returns_none_without_db() -> None:
    app = Flask(__name__)

    with app.app_context():
        assert build_memory_manager() is None


def test_build_memory_manager_uses_auth_db_path() -> None:
    app = Flask(__name__)

    with app.app_context():
        db_stub = _AuthDbStub("/tmp/test-auth.sqlite3")
        app.extensions["auth_db"] = db_stub

        manager = build_memory_manager()
        assert manager is not None
        assert str(manager.db_path) == "/tmp/test-auth.sqlite3"
