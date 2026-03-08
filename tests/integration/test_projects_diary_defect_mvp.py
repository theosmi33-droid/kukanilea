from __future__ import annotations

import sqlite3

from app import create_app


def _seed_session(client, *, tenant: str, user: str = "dev", role: str = "DEV") -> None:
    with client.session_transaction() as sess:
        sess["user"] = user
        sess["role"] = role
        sess["tenant_id"] = tenant


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    return app, app.test_client()


def _payload(source: str = "upload") -> dict:
    return {
        "source": source,
        "thread_id": "thread-99",
        "sender": "kunde@example.com",
        "subject": "Baustelle Musterweg",
        "snippets": ["Wand im Bad hat Riss", "Fensterrahmen beschädigt"],
        "diary_text": "Tagesbericht: Schäden nach Lieferung dokumentiert.",
        "defects": [
            {
                "title": "Riss in Wand",
                "description": "Im Bad links neben Tür.",
                "status": "OPEN",
                "photos": ["photo://wand-1.jpg"],
            },
            {
                "title": "Fensterrahmen defekt",
                "description": "Lack abgeplatzt",
                "status": "IN_PROGRESS",
                "photos": ["photo://fenster-1.jpg", "photo://fenster-2.jpg"],
            },
        ],
    }


def test_projects_diary_payload_normalize_keeps_defect_items(tmp_path, monkeypatch):
    _app, client = _bootstrap(tmp_path, monkeypatch)
    _seed_session(client, tenant="KUKANILEA")

    response = client.post("/api/intake/normalize", json=_payload("messenger"))
    assert response.status_code == 200
    envelope = response.get_json()["envelope"]

    assert envelope["source"] == "messenger"
    assert envelope["diary_entry"]["body"].startswith("Tagesbericht")
    assert len(envelope["defects"]) == 2
    assert envelope["defects"][0]["status"] == "OPEN"
    assert envelope["defects"][1]["photos"] == ["photo://fenster-1.jpg", "photo://fenster-2.jpg"]


def test_projects_diary_and_defect_execute_persists_and_updates_summary(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)
    _seed_session(client, tenant="KUKANILEA")

    envelope = client.post("/api/intake/normalize", json=_payload("upload")).get_json()["envelope"]
    response = client.post(
        "/api/intake/execute",
        json={"envelope": envelope, "requires_confirm": True, "confirm": "YES"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "executed"
    assert body["diary"] is not None
    assert len(body["defects"]) == 2

    con = sqlite3.connect(app.config["AUTH_DB"])
    try:
        diary_count = con.execute(
            "SELECT COUNT(*) FROM project_diary_entries WHERE tenant_id = ?", ("KUKANILEA",)
        ).fetchone()[0]
        defect_open_count = con.execute(
            "SELECT COUNT(*) FROM project_defects WHERE tenant_id = ? AND status IN ('OPEN', 'IN_PROGRESS')",
            ("KUKANILEA",),
        ).fetchone()[0]
    finally:
        con.close()

    assert diary_count == 1
    assert defect_open_count == 2

    summary = client.get("/api/projects/summary")
    assert summary.status_code == 200
    summary_body = summary.get_json()
    assert summary_body["metrics"]["open_defects"] == 2
    assert "defects_open" not in summary_body["metrics"]
    assert "overdue_tasks" in summary_body["metrics"]
    assert "active_projects" in summary_body["metrics"]
