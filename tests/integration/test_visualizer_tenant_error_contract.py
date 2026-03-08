from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

from app import create_app


def test_visualizer_render_cross_tenant_error_contract(tmp_path):
    from app.auth import hash_password

    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = "2026-03-08T00:00:00Z"
        auth_db.upsert_tenant("tenant-x", "tenant-x", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "tenant-x", "DEV", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "tenant-x"
        sess["csrf_token"] = "csrf-test"

    foreign = Path(tmp_path) / "tenant-y" / "secret.csv"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("x,y\n1,2\n", encoding="utf-8")
    encoded = base64.b64encode(str(foreign).encode("utf-8")).decode("ascii")

    with patch("app.routes.visualizer.BASE_PATH", Path(tmp_path)), patch(
        "app.routes.visualizer._is_allowed_path", return_value=True
    ), patch("app.routes.visualizer.current_tenant", return_value="tenant-x"):
        response = client.get(f"/api/visualizer/render?source={encoded}")

    assert response.status_code == 403
    assert response.get_json() == {"error": "forbidden_tenant_path"}
