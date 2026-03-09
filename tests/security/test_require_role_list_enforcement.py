from __future__ import annotations

from flask import jsonify

from app.auth import login_required, require_role


def test_require_role_with_allowlist_blocks_readonly(admin_client):
    app, client = admin_client

    @app.route("/api/__test-role-list", methods=["GET"])
    @login_required
    @require_role(["DEV", "ADMIN"])
    def _test_role_list():
        return jsonify(ok=True)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "READONLY"
        sess["tenant_id"] = "KUKANILEA"

    denied = client.get("/api/__test-role-list")
    assert denied.status_code == 403

    with client.session_transaction() as sess:
        sess["role"] = "ADMIN"

    allowed = client.get("/api/__test-role-list")
    assert allowed.status_code == 200
    assert allowed.get_json()["ok"] is True

