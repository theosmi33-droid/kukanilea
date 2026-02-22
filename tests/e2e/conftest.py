from __future__ import annotations

from datetime import UTC, datetime
from threading import Thread

import pytest
from werkzeug.serving import make_server

import app.web as webmod
import kukanilea_core_v3_fixed as coremod
from app import create_app
from app.auth import hash_password


@pytest.fixture(scope="session")
def e2e_app(tmp_path_factory: pytest.TempPathFactory):
    tmp_dir = tmp_path_factory.mktemp("e2e")
    core_db_path = tmp_dir / "core_e2e.sqlite3"

    app = create_app()
    app.config.update(TESTING=True, READ_ONLY=False)

    # Keep e2e data deterministic and isolated from the default core db path.
    webmod.core.DB_PATH = core_db_path
    coremod.DB_PATH = core_db_path
    app.config["CORE_DB"] = core_db_path

    if webmod.db_init is not None:
        webmod.db_init()

    now = datetime.now(UTC).isoformat(timespec="seconds")
    auth_db = app.extensions["auth_db"]
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    if auth_db.get_user("e2e_admin") is None:
        auth_db.create_user(
            username="e2e_admin",
            password_hash=hash_password("e2e_admin"),
            created_at=now,
            email="e2e_admin@demo.invalid",
            email_verified=1,
        )
    auth_db.upsert_membership("e2e_admin", "KUKANILEA", "ADMIN", now)

    return app


@pytest.fixture(scope="session")
def e2e_server(e2e_app):
    server = make_server("127.0.0.1", 0, e2e_app)
    host, port = server.server_address
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def base_url(e2e_server: str) -> str:
    return e2e_server
