from __future__ import annotations

import json
import sqlite3
from tests.time_utils import utc_now_iso

from pathlib import Path



def _make_app(tmp_path: Path, monkeypatch):
    from app import create_app
    from app.auth import hash_password
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
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

    return app


def test_license_status_flow_active_grace_blocked(monkeypatch, tmp_path: Path):
    from app import license as license_mod

    base = {
        "valid": True,
        "plan": "ENTERPRISE",
        "expired": False,
        "device_mismatch": False,
    }
    statuses = [
        ("active", False, "ok"),
        ("grace", True, "grace_read_only"),
        ("gesperrt", True, "license_blocked_smb_unreachable"),
    ]
    for status, expected_read_only, expected_reason in statuses:
        monkeypatch.setattr(license_mod, "load_license", lambda _p, s=status: {**base, "status": s})
        if status == "gesperrt":
            monkeypatch.setenv("KUKANILEA_SMB_REACHABLE", "0")
        else:
            monkeypatch.delenv("KUKANILEA_SMB_REACHABLE", raising=False)
        state = license_mod.load_runtime_license_state(
            license_path=tmp_path / "license.json",
            trial_path=tmp_path / "trial.json",
        )
        assert state["status"] in {"active", "grace", "blocked"}
        assert state["read_only"] is expected_read_only
        assert state["reason"] == expected_reason


def test_license_upload_refreshes_runtime_state_and_writes_audit(monkeypatch, tmp_path: Path):
    import app.routes.admin_tenants as admin_routes

    app = _make_app(tmp_path, monkeypatch)
    app.config["READ_ONLY"] = True
    app.config["LICENSE_REASON"] = "license_blocked_smb_unreachable"
    app.config["LICENSE_STATUS"] = "blocked"

    monkeypatch.setattr(admin_routes, "load_license", lambda _p: {"valid": True, "plan": "ENTERPRISE"})
    monkeypatch.setattr(
        admin_routes,
        "load_runtime_license_state",
        lambda **_kwargs: {
            "plan": "ENTERPRISE",
            "trial": False,
            "trial_days_left": 0,
            "expired": False,
            "device_mismatch": False,
            "read_only": False,
            "reason": "ok",
            "status": "active",
        },
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "test-csrf"

    response = client.post(
        "/admin/settings/license/upload",
        data={"license_json": '{"plan":"ENTERPRISE"}', "confirm": "YES", "csrf_token": "test-csrf"},
    )
    assert response.status_code in {302, 303}
    assert app.config["READ_ONLY"] is False
    assert app.config["LICENSE_STATUS"] == "active"
    assert app.config["LICENSE_REASON"] == "ok"

    con = sqlite3.connect(app.config["CORE_DB"])
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT action, meta_json FROM audit WHERE action IN ('LICENSE_UPLOAD','LICENSE_STATE_APPLIED') ORDER BY id"
        ).fetchall()
    finally:
        con.close()
    actions = [str(row["action"]) for row in rows]
    assert "LICENSE_UPLOAD" in actions
    assert "LICENSE_STATE_APPLIED" in actions
    applied_row = next(row for row in rows if str(row["action"]) == "LICENSE_STATE_APPLIED")
    applied_meta = json.loads(str(applied_row["meta_json"]))
    assert applied_meta["from_status"] == "blocked"
    assert applied_meta["from_read_only"] is True
    assert applied_meta["to_status"] == "active"
    assert applied_meta["to_read_only"] is False


def test_settings_page_exposes_backup_paths_and_hooks(tmp_path: Path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    response = client.get("/admin/settings")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-testid="backup-run-form"' in html
    assert 'data-testid="backup-restore-form"' in html
    assert 'data-testid="license-upload-form"' in html
    assert 'data-testid="backup-target-auth.sqlite3"' in html
    assert str((tmp_path / "auth.sqlite3").resolve()) in html




def test_settings_page_exposes_ops_release_stubs_and_defaults(tmp_path: Path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    response = client.get("/admin/settings")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-testid="tenant-stub-status"' in html
    assert 'data-testid="roles-stub-status"' in html
    assert 'data-testid="policies-stub-status"' in html
    assert 'name="memory_retention_days" value="60"' in html
    assert 'name="external_apis_enabled"' in html
    assert 'name="external_translation_enabled"' in html


def test_system_settings_defaults_external_api_off_and_retention_60(tmp_path: Path, monkeypatch):
    from app.routes.admin_tenants import _load_system_settings
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)

    settings = _load_system_settings()
    assert settings["external_apis_enabled"] is False
    assert settings["external_translation_enabled"] is False
    assert settings["memory_retention_days"] == 60
    assert settings["backup_verify_hook_enabled"] is True
    assert settings["restore_verify_hook_enabled"] is True

def test_restore_backup_rejects_path_traversal(tmp_path: Path, monkeypatch):
    from app.config import Config
    from app.routes import admin_tenants

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(Config, "AUTH_DB", tmp_path / "auth.sqlite3")
    monkeypatch.setattr(Config, "CORE_DB", tmp_path / "core.sqlite3")
    monkeypatch.setattr(Config, "LICENSE_PATH", tmp_path / "license.json")

    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    evil = tmp_path / "evil.bak"
    evil.write_text("x", encoding="utf-8")

    try:
        admin_tenants._restore_backup("../evil.bak")
        assert False, "expected invalid backup path"
    except ValueError as exc:
        assert str(exc) in {"backup_not_found", "invalid_backup_path"}
