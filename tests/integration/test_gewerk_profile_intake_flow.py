from __future__ import annotations

from app import create_app


def _seed_session(client) -> None:
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"


def test_intake_profile_enrichment_and_matrix_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    client = app.test_client()
    _seed_session(client)

    normalized = client.post(
        "/api/intake/normalize",
        json={"source": "mail", "subject": "Prüfung", "profile_id": "elektro", "snippets": ["Bitte prüfen"]},
    )
    assert normalized.status_code == 200
    body = normalized.get_json()
    assert body["envelope"]["profile_id"] == "elektro"
    assert body["profile"]["gewerk_name"] == "Elektro"

    matrix_resp = client.get("/api/gewerke/matrix")
    assert matrix_resp.status_code == 200
    matrix_body = matrix_resp.get_json()
    assert matrix_body["action_ledger"]["total_actions"] >= 2000
    assert len(matrix_body["matrix"]) >= 20
