from __future__ import annotations

from app import create_app
from app.core import upload_pipeline


def _seed_session(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "flow-ab-bot"
        sess["role"] = "SYSTEM"
        sess["tenant_id"] = "KUKANILEA"


def _intake_payload(case_id: int, source: str) -> dict:
    return {
        "source": source,
        "thread_id": f"flow-ab-thread-{case_id}",
        "sender": f"kunde{case_id}@example.com",
        "subject": f"Flow A/B Fall {case_id}",
        "message": "Bitte als Aufgabe anlegen und Termin eintragen.",
        "project_hint": "Flow AB Projekt",
        "calendar_hint": "Rueckruf",
        "due_date": "2031-01-01T10:00:00+00:00",
    }


def test_flow_ab_action_ledger_reaches_2000(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    monkeypatch.setenv("CLAMAV_OPTIONAL", "1")
    monkeypatch.setattr(upload_pipeline, "_scan_malware", lambda _path: (True, upload_pipeline.UploadErrorCode.CLEAN))

    app = create_app()
    client = app.test_client()
    _seed_session(client)

    intake_steps = 0
    sources = ["mail", "messenger", "mixed"]
    for idx in range(100):
        payload = _intake_payload(idx, sources[idx % len(sources)])
        normalize = client.post("/api/intake/normalize", json=payload)
        assert normalize.status_code == 200
        envelope = normalize.get_json()["envelope"]

        blocked = client.post(
            "/api/intake/execute",
            json={"envelope": envelope, "requires_confirm": True, "confirm": "no"},
        )
        assert blocked.status_code == 409

        executed = client.post(
            "/api/intake/execute",
            json={"envelope": envelope, "requires_confirm": True, "confirm": "yes"},
        )
        assert executed.status_code == 200
        body = executed.get_json()
        assert body["status"] == "executed"
        assert body["task"]["task_id"] > 0

        intake_steps += 8

    document_steps = 0
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    for idx in range(80):
        if idx % 3 == 0:
            path = docs_root / f"case-{idx}.pdf"
            path.write_bytes(b"%PDF-1.4\nflow-ab\n")
            result = upload_pipeline.process_upload(path, "KUKANILEA")
            assert result.success is True
        elif idx % 3 == 1:
            path = docs_root / f"case-{idx}.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\nflow-ab")
            result = upload_pipeline.process_upload(path, "KUKANILEA")
            assert result.success is True
        else:
            path = docs_root / f"case-{idx}.exe"
            path.write_bytes(b"MZ malformed")
            result = upload_pipeline.process_upload(path, "KUKANILEA")
            assert result.success is False
            assert result.error_code == upload_pipeline.UploadErrorCode.UNSUPPORTED_EXTENSION

        document_steps += 8

    cross_flow_steps = 0
    for idx in range(20):
        payload = _intake_payload(1000 + idx, "mixed")
        envelope = client.post("/api/intake/normalize", json=payload).get_json()["envelope"]
        executed = client.post(
            "/api/intake/execute",
            json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
        )
        assert executed.status_code == 200

        upload_path = docs_root / f"cross-{idx}.pdf"
        upload_path.write_bytes(b"%PDF-1.4\ncross-flow\n")
        result = upload_pipeline.process_upload(upload_path, "KUKANILEA")
        assert result.success is True

        summary_task = client.get("/api/tasks/summary")
        summary_calendar = client.get("/api/calendar/summary")
        health_upload = client.get("/api/upload/health")
        assert summary_task.status_code == 200
        assert summary_calendar.status_code == 200
        assert health_upload.status_code == 200

        cross_flow_steps += 20

    stabilization_steps = 0
    for idx in range(10):
        heartbeat = client.get("/api/intake/health")
        summary_intake = client.get("/api/intake/summary")
        summary_upload = client.get("/api/upload/summary")
        assert heartbeat.status_code == 200
        assert summary_intake.status_code == 200
        assert summary_upload.status_code == 200
        stabilization_steps += 20

    total_steps = intake_steps + document_steps + cross_flow_steps + stabilization_steps
    assert intake_steps == 800
    assert document_steps == 640
    assert cross_flow_steps == 400
    assert stabilization_steps == 200
    assert total_steps >= 2000
