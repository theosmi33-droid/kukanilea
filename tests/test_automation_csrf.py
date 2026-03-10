import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password
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


def _seed_operator(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("operator", hash_password("secret"), now)
        auth_db.upsert_membership("operator", "KUKANILEA", "OPERATOR", now)


def _login_operator(client):
    with client.session_transaction() as sess:
        sess["user"] = "operator"
        sess["role"] = "OPERATOR"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"


def test_automation_rule_create_rejects_missing_csrf(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_operator(app)
    client = app.test_client()
    _login_operator(client)

    resp = client.post(
        "/automation/rules/create",
        data={
            "name": "",
            "scope": "leads",
            "condition_kind": "lead_overdue",
            "condition_json": '{"days_overdue":1,"status_in":["new"],"priority_in":["normal"]}',
            "action_list_json": '[{"kind":"lead_pin","value":true}]',
        },
    )

    assert resp.status_code == 403


def test_automation_rule_create_accepts_valid_csrf(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_operator(app)
    client = app.test_client()
    _login_operator(client)

    resp = client.post(
        "/automation/rules/create",
        data={
            "csrf_token": "csrf-test",
            "name": "",
            "scope": "leads",
            "condition_kind": "lead_overdue",
            "condition_json": '{"days_overdue":1,"status_in":["new"],"priority_in":["normal"]}',
            "action_list_json": '[{"kind":"lead_pin","value":true}]',
        },
    )

    assert resp.status_code == 400
