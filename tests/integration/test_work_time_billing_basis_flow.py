from __future__ import annotations

import csv
import io
import re
import sqlite3

import pytest

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


def _seed_admin(app) -> None:
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("admin", hash_password("adminpass"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "csrf token not found"
    return str(match.group(1))


def _login(client) -> None:
    login_page = client.get("/login")
    assert login_page.status_code == 200
    csrf_token = _extract_csrf(login_page.get_data(as_text=True))

    response = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "adminpass",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}


@pytest.mark.integration
def test_work_to_time_to_billing_basis_flow_is_consistent(tmp_path, monkeypatch):
    from app import core

    app = _make_app(tmp_path, monkeypatch)
    _seed_admin(app)

    with app.app_context():
        tenant = "KUKANILEA"
        approved = core.time_entry_start(
            tenant_id=tenant,
            user="admin",
            started_at="2026-03-02T08:00:00+00:00",
            note="Montage",
            entry_type="WORK",
        )
        core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(approved["id"]),
            ended_at="2026-03-02T09:00:00+00:00",
        )
        core.time_entry_approve(tenant_id=tenant, entry_id=int(approved["id"]), approved_by="admin")

        pending = core.time_entry_start(
            tenant_id=tenant,
            user="admin",
            started_at="2026-03-02T10:00:00+00:00",
            note="Noch offen",
            entry_type="WORK",
        )
        core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(pending["id"]),
            ended_at="2026-03-02T10:30:00+00:00",
        )

        sick = core.time_entry_start(
            tenant_id=tenant,
            user="admin",
            started_at="2026-03-02T11:00:00+00:00",
            note="krank",
            entry_type="SICK",
        )
        core.time_entry_stop(
            tenant_id=tenant,
            user="admin",
            entry_id=int(sick["id"]),
            ended_at="2026-03-02T12:00:00+00:00",
        )
        core.time_entry_approve(tenant_id=tenant, entry_id=int(sick["id"]), approved_by="admin")

    client = app.test_client()
    _login(client)

    export_response = client.get("/api/time/export?range=day&date=2026-03-02&basis=billing")
    assert export_response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(export_response.get_data(as_text=True))))

    assert len(rows) == 1
    assert int(rows[0]["entry_id"]) == int(approved["id"])
    assert rows[0]["approval_status"] == "APPROVED"
    assert rows[0]["entry_type"] == "WORK"

    summary = client.get("/api/zeiterfassung/summary")
    assert summary.status_code == 200
    body = summary.get_json()
    assert body["metrics"]["billing_basis_entries"] == 1
    assert body["metrics"]["billing_basis_seconds"] == 3600

    with sqlite3.connect(app.config["CORE_DB"]) as con:
        actions = [
            row[0]
            for row in con.execute(
                "SELECT action FROM audit WHERE target=? ORDER BY id",
                (str(approved["id"]),),
            ).fetchall()
        ]
    assert actions == ["TIME_ENTRY_START", "TIME_ENTRY_STOP", "TIME_ENTRY_APPROVE"]
