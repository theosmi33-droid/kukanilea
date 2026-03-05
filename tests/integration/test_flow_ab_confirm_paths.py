from __future__ import annotations

import sqlite3

import pytest

from app import create_app


def _seed_session(client, *, tenant: str, user: str = "dev", role: str = "DEV") -> None:
    with client.session_transaction() as sess:
        sess["user"] = user
        sess["role"] = role
        sess["tenant_id"] = tenant


def _bootstrap_client(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    return app, app.test_client()


def _payload(seq: int = 1) -> dict:
    return {
        "source": "mail",
        "thread_id": f"flow-confirm-{seq:04d}",
        "sender": "kunde@example.com",
        "subject": f"Flow Confirm Test {seq}",
        "snippets": [f"Bitte Aufgabe {seq} planen."],
        "attachments": [{"filename": f"anhang-{seq}.pdf", "id": f"att-{seq}", "content_type": "application/pdf"}],
        "project_hint": "Projekt Confirm",
        "calendar_hint": "Rueckruf",
        "due_date": "2030-06-01T08:00:00+00:00",
    }


def _tasks_per_tenant(db_path: str) -> dict[str, int]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("SELECT tenant, COUNT(*) FROM tasks GROUP BY tenant ORDER BY tenant").fetchall()
    finally:
        con.close()
    return {str(tenant): int(count) for tenant, count in rows}


def test_intake_execute_requires_confirm_flag(tmp_path, monkeypatch):
    _app, client = _bootstrap_client(tmp_path, monkeypatch)
    _seed_session(client, tenant="KUKANILEA")

    envelope = client.post("/api/intake/normalize", json=_payload(1)).get_json()["envelope"]
    response = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": False, "confirm": "YES"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "confirm_required_flag_missing"


@pytest.mark.parametrize("confirm_value", ["", "no", "0", "false"])
def test_intake_execute_blocks_without_explicit_confirm(tmp_path, monkeypatch, confirm_value: str):
    _app, client = _bootstrap_client(tmp_path, monkeypatch)
    _seed_session(client, tenant="KUKANILEA")

    envelope = client.post("/api/intake/normalize", json=_payload(2)).get_json()["envelope"]
    response = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": confirm_value},
    )

    body = response.get_json()
    assert response.status_code == 409
    assert body["status"] == "blocked"
    assert body["error"] == "explicit_confirm_required"


@pytest.mark.parametrize("confirm_value", ["YES", "y", "true", "1"])
def test_intake_execute_accepts_truthy_confirm_aliases(tmp_path, monkeypatch, confirm_value: str):
    app, client = _bootstrap_client(tmp_path, monkeypatch)
    _seed_session(client, tenant="KUKANILEA")

    envelope = client.post("/api/intake/normalize", json=_payload(3)).get_json()["envelope"]
    response = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": confirm_value},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "executed"
    assert int(body["task"]["task_id"]) > 0

    with app.app_context():
        per_tenant = _tasks_per_tenant(app.config["CORE_DB"])
    assert per_tenant.get("kukanilea", 0) == 1


def test_intake_execute_writes_per_tenant_task_rows(tmp_path, monkeypatch):
    app, client = _bootstrap_client(tmp_path, monkeypatch)

    _seed_session(client, tenant="ALPHA")
    envelope_a = client.post("/api/intake/normalize", json=_payload(10)).get_json()["envelope"]
    resp_a = client.post(
        "/api/intake/execute",
        json={"envelope": envelope_a, "requires_confirm": True, "confirm": "YES"},
    )
    assert resp_a.status_code == 200

    _seed_session(client, tenant="BETA")
    envelope_b = client.post("/api/intake/normalize", json=_payload(11)).get_json()["envelope"]
    resp_b = client.post(
        "/api/intake/execute",
        json={"envelope": envelope_b, "requires_confirm": True, "confirm": "YES"},
    )
    assert resp_b.status_code == 200

    with app.app_context():
        per_tenant = _tasks_per_tenant(app.config["CORE_DB"])
    assert per_tenant == {"alpha": 1, "beta": 1}


def test_upload_summary_reflects_active_tenant_session(tmp_path, monkeypatch):
    _app, client = _bootstrap_client(tmp_path, monkeypatch)
    _seed_session(client, tenant="TENANT_X")

    response = client.get("/api/upload/summary")
    assert response.status_code == 200
    body = response.get_json()
    assert body["tool"] == "upload"
    assert body["summary"]["details"]["tenant"] == "TENANT_X"

    contract = body["summary"]["details"]["intake_contract"]
    assert contract["normalize_endpoint"] == "/api/intake/normalize"
    assert contract["execute_endpoint"] == "/api/intake/execute"
    assert contract["requires_explicit_confirm"] is True
