from __future__ import annotations

from tests.time_utils import utc_now_iso



def _make_app(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")
    app = create_app()
    app.config["TESTING"] = True
    return app


def _auth_client(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
    return client


def test_dashboard_matrix_returns_all_tools(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    response = client.get("/api/dashboard/tool-matrix")
    assert response.status_code == 200

    body = response.get_json()
    assert body["ok"] is True
    assert body["total"] == 11
    assert body["read_only_contract"] is True
    assert len(body["tools"]) == 11

    for row in body["tools"]:
        assert isinstance(row.get("metrics"), dict)
        assert isinstance(row.get("details"), dict)
        assert isinstance(row["details"].get("contract"), dict)


def test_dashboard_matrix_marks_degraded_tool_instead_of_hard_fail(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = _auth_client(app)

    import app.contracts.tool_contracts as contracts

    def _broken_upload(_tenant):
        return {"pending_items": 0}, {"source": "broken"}, "simulated_gateway_unavailable"

    monkeypatch.setattr(contracts, "_collect_upload_summary", _broken_upload)
    contracts.SUMMARY_COLLECTORS["upload"] = _broken_upload

    response = client.get("/api/dashboard/tool-matrix")
    assert response.status_code == 200
    body = response.get_json()

    assert "upload" in body["degraded"]
    upload = next(row for row in body["tools"] if row["tool"] == "upload")
    assert upload["status"] == "degraded"
    assert upload["degraded_reason"] == "simulated_gateway_unavailable"
    assert upload["details"]["contract"]["read_only"] is False
