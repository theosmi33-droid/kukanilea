import sys
from pathlib import Path

from tests.time_utils import utc_now_iso

sys.path.append(str(Path(__file__).resolve().parents[1]))




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


def test_sidebar_toggle_persistence_and_running_badges_markup(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.get("/", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "id=\"sidebar-toggle\"" in html
    assert "ks_sidebar_collapsed" in html
    assert "id=\"outbound-status-badges\"" in html



def test_sidebar_disables_hx_boost_for_full_page_navigation(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.get("/", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert '<nav class="sidebar" hx-boost="false"' in html


def test_sidebar_main_tabs_have_consistent_semantics(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.get("/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    main_tabs = [
        "dashboard",
        "upload",
        "projects",
        "tasks",
        "messenger",
        "email",
        "calendar",
        "time",
        "visualizer",
        "settings",
    ]
    for tab in main_tabs:
        assert f'data-nav-key="{tab}"' in html

    assert html.count('data-nav-active="') >= len(main_tabs)
    assert html.count('aria-current="') >= len(main_tabs)


def test_page_ready_marker_present_on_main_content(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.get("/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="main-content" hx-history-elt data-page-ready="1"' in html


def test_skip_link_and_aria_labels_are_present(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        from app.auth import hash_password

        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    resp = client.get("/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert 'class="skip-link" href="#app-main"' in html
    assert 'data-nav-mode="full-page"' in html
    assert 'aria-label="Sovereign-11 Hauptseiten"' in html
    assert 'aria-label="Assistant öffnen"' in html


def test_sidebar_icon_sprite_references_exist() -> None:
    import re

    sidebar = Path("app/templates/partials/sidebar.html").read_text(encoding="utf-8")
    layout = Path("app/templates/layout.html").read_text(encoding="utf-8")
    sprite = Path("app/static/icons/sprite.svg").read_text(encoding="utf-8")

    refs = set(re.findall(r"/static/icons/sprite\.svg#([a-z0-9-]+)", sidebar + layout))
    symbols = set(re.findall(r'<symbol\s+id="([a-z0-9-]+)"', sprite))

    assert refs
    assert refs <= symbols


def test_sidebar_primary_tab_order_contract() -> None:
    html = Path("app/templates/partials/sidebar.html").read_text(encoding="utf-8")
    ordered_keys = [
        "dashboard",
        "upload",
        "email",
        "messenger",
        "calendar",
        "tasks",
        "time",
        "projects",
        "visualizer",
        "settings",
    ]
    positions = [html.index(f"'key': '{key}'") for key in ordered_keys]
    assert positions == sorted(positions)
