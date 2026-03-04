from __future__ import annotations

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
        ("grace", False, "grace"),
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
