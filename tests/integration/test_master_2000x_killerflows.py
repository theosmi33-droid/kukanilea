from __future__ import annotations

from app import create_app
from app.auth import hash_password
from tests.time_utils import utc_now_iso
from app.mail.intake import normalize_intake_payload
from app import api as api_module
from app.modules.zeiterfassung import contracts as time_contracts




def _seed_auth(app) -> None:
    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = utc_now_iso()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)
        auth_db.upsert_user("admin", hash_password("admin"), now)
        auth_db.upsert_membership("admin", "KUKANILEA", "ADMIN", now)

def _seed_session(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"


def test_flow_a_anfrage_task_projekt_termin_confirmed(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    _seed_auth(app)
    client = app.test_client()
    _seed_session(client)

    monkeypatch.setattr(api_module, "create_project", lambda **kwargs: {"project_id": 42, "name": kwargs["name"]})
    monkeypatch.setattr(api_module, "create_event", lambda **kwargs: {"event_id": 7, "title": kwargs["title"]})

    normalized = client.post(
        "/api/intake/normalize",
        json={
            "source": "mail",
            "thread_id": "th-2000",
            "sender": "kunde@example.com",
            "subject": "Bitte Angebot abstimmen",
            "snippets": ["Bitte als Task anlegen."],
            "project_hint": "Projekt Master 2000X",
            "calendar_hint": "Angebotstermin",
            "due_date": "2030-05-01T10:00:00+00:00",
        },
    )
    envelope = normalized.get_json()["envelope"]

    response = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["status"] == "executed"
    assert body["task"]["task_id"] > 0
    assert body["project"] and body["project"]["name"] == "Projekt Master 2000X"
    assert body["calendar"] and body["calendar"]["title"] == "Angebotstermin"


def test_flow_b_dokument_extraktion_due_and_assignment_mapping():
    envelope = normalize_intake_payload(
        {
            "source": "mail",
            "thread_id": "doc-1",
            "sender": "ops@example.com",
            "subject": "Vertrag mit Frist",
            "snippets": ["Bitte bis Monatsende zuordnen"],
            "attachments": [{"filename": "vertrag.pdf", "content_type": "application/pdf", "id": "att-77"}],
            "project_hint": "Projekt Vertragsimport",
            "due_date": "2030-06-30T17:00:00+00:00",
        }
    )
    assert envelope.attachments[0]["name"] == "vertrag.pdf"
    assert envelope.attachments[0]["media_type"] == "application/pdf"
    assert envelope.attachments[0]["handoff_ref"] == "att-77"
    assert envelope.suggested_actions[0]["project_hint"] == "Projekt Vertragsimport"
    assert envelope.suggested_actions[0]["due_date"] == "2030-06-30T17:00:00+00:00"
    assert envelope.requires_confirm is True


def test_flow_c_time_to_billable_basis(monkeypatch):
    monkeypatch.setattr(
        time_contracts.core,
        "time_entry_list",
        lambda tenant: [
            {"duration_seconds": 3600, "approval_status": "APPROVED", "ended_at": "2030-01-01T11:00:00+00:00"},
            {"duration_seconds": 1200, "approval_status": "PENDING", "ended_at": "2030-01-01T12:00:00+00:00"},
            {"duration_seconds": 300, "approval_status": "READY", "ended_at": "2030-01-01T13:00:00+00:00"},
            {"duration_seconds": 0, "approval_status": "APPROVED", "ended_at": None},
        ],
        raising=False,
    )
    payload = time_contracts.build_summary("KUKANILEA")
    metrics = payload["metrics"]
    assert metrics["entries"] == 4
    assert metrics["running"] == 1
    assert metrics["total_duration_seconds"] == 5100
    assert metrics["billable_basis_seconds"] == 3900


def test_flow_d_backup_restore_confirm_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    _seed_auth(app)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "admin"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    response = client.post(
        "/admin/settings/backup/restore",
        data={"backup_name": "missing.bak"},
        follow_redirects=True,
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body and body["error"] == "confirm_required"
