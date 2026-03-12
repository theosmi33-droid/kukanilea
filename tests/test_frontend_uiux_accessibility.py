import re

import pytest

from app.auth import hash_password
from tests.time_utils import utc_now_iso

# KUKANILEA Accessibility Tests (Worker 4: Page UX Polish + QA)

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
    app.config["SERVER_NAME"] = "localhost" # Required for url_for
    return app

def _seed_admin(app):
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("adminpass"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

def _login(client):
    html = client.get("/login").get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html)
    client.post("/login", data={
        "username": "admin", "password": "adminpass", "csrf_token": csrf.group(1)
    })

@pytest.fixture
def client(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)
    with app.test_client() as client:
        _login(client)
        yield client

@pytest.mark.parametrize("path", ["/dashboard", "/upload", "/projects"])
def test_page_accessibility_landmarks(client, path):
    """Checks for presence of basic A11y landmarks."""
    response = client.get(path)
    html = response.get_data(as_text=True)
    assert "<main" in html or 'role="main"' in html
    assert "<nav" in html or 'role="navigation"' in html
    assert 'class="skip-link"' in html
    assert "<title>" in html

@pytest.mark.parametrize("path", ["/dashboard", "/upload", "/projects"])
def test_page_accessibility_labels(client, path):
    """Checks for aria-labels or semantic labels on critical interactive elements."""
    response = client.get(path)
    html = response.get_data(as_text=True)
    # Check for presence of labels or aria attributes
    assert 'aria-label="' in html or 'aria-labelledby="' in html or "<label" in html or 'title="' in html

def test_dashboard_focus_management(client):
    """Ensures dashboard has a clear focus entry point via layout.html target."""
    response = client.get("/dashboard")
    html = response.get_data(as_text=True)
    # Main content should be focusable via skip link target
    assert 'id="app-main" tabindex="-1"' in html


@pytest.mark.parametrize(
    "path, expected_title",
    [
        ("/assistant", "Assistant"),
        ("/time", "Zeiterfassung"),
        ("/admin/mesh", "Mesh-Admin"),
    ],
)
def test_inline_fragment_pages_have_descriptive_page_titles(client, path, expected_title):
    response = client.get(path)
    html = response.get_data(as_text=True)
    title = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    assert title is not None
    assert expected_title in title.group(1)
