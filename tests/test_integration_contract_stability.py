from __future__ import annotations

import pytest

from app.contracts.tool_contracts import CONTRACT_TOOLS
from tests.time_utils import utc_now_iso

STANDARD_FIELDS = {"tool", "status", "ts", "summary", "warnings", "links"}
ALL_TOOLS = [*CONTRACT_TOOLS, "kalender", "aufgaben", "zeiterfassung", "projekte", "einstellungen"]


def _make_auth_client(tmp_path, monkeypatch):
    from app import create_app
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")
    monkeypatch.setattr(Config, "TRIAL_PATH", tmp_path / "trial.json")
    app = create_app()
    app.config["TESTING"] = True

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


@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    return _make_auth_client(tmp_path, monkeypatch)


@pytest.mark.parametrize("tool", ALL_TOOLS)
@pytest.mark.parametrize("endpoint", ["summary", "health"])
def test_contract_shape_and_status_codes(auth_client, tool, endpoint):
    response = auth_client.get(f"/api/{tool}/{endpoint}")
    assert response.status_code in {200, 500, 503}, f"{tool}/{endpoint}: invalid status code {response.status_code}"

    body = response.get_json()
    assert isinstance(body, dict), f"{tool}/{endpoint}: payload must be JSON object"
    assert STANDARD_FIELDS.issubset(body.keys()), f"{tool}/{endpoint}: missing standard contract fields"
    assert body["tool"] == tool
    assert body["status"] in {"ok", "degraded", "down"}
    assert isinstance(body["ts"], str) and body["ts"], f"{tool}/{endpoint}: missing ts"
    assert isinstance(body["summary"], dict), f"{tool}/{endpoint}: summary must be object"
    assert isinstance(body["warnings"], list), f"{tool}/{endpoint}: warnings must be array"
    assert isinstance(body["links"], list), f"{tool}/{endpoint}: links must be array"

    if body["status"] == "ok":
        assert response.status_code == 200, f"{tool}/{endpoint}: ok must return 200"
    if body["status"] == "degraded":
        assert response.status_code == 503, f"{tool}/{endpoint}: degraded must return 503"
    if body["status"] == "down":
        assert response.status_code in {500, 503}, f"{tool}/{endpoint}: down must return 500/503"
