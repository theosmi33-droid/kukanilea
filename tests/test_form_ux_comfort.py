import re
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


def _seed_admin(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("adminpass"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)


def test_login_form_has_grouping_hints_and_alert_semantics(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    client = app.test_client()

    html = client.get("/login").get_data(as_text=True)

    assert 'class="login-fieldset"' in html
    assert 'id="username-hint"' in html
    assert 'id="password-hint"' in html
    assert 'autocomplete="username"' in html
    assert 'autocomplete="current-password"' in html

    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert csrf
    invalid = client.post(
        "/login",
        data={"username": "admin", "password": "wrong", "csrf_token": csrf.group(1)},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert 'role="alert" aria-live="assertive"' in invalid


def test_onboarding_form_uses_progressive_disclosure_for_optional_credentials(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/onboarding", follow_redirects=False)
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'id="advanced-bootstrap"' in html
    assert 'Zugangsdaten selbst festlegen (optional)' in html
    assert 'id="admin-user"' in html
    assert 'id="admin-pass"' in html
    assert 'Leer lassen = automatisch generiertes Einmal-Passwort.' in html
