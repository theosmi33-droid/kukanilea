import sys
from datetime import datetime
from pathlib import Path

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


def _seed_user(app):
    from app.auth import hash_password

    with app.app_context():
        auth_db = app.extensions["auth_db"]
        now = datetime.utcnow().isoformat()
        auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)


def _login(client):
    with client.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"


def test_visualizer_route_and_api_smoke(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_user(app)
    client = app.test_client()
    _login(client)

    import app.web as web

    tenant_in = web.EINGANG / "kukanilea"
    tenant_in.mkdir(parents=True, exist_ok=True)
    doc = tenant_in / "smoke.txt"
    doc.write_text("Hallo Visualizer", encoding="utf-8")

    # UI route
    resp = client.get("/visualizer")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "The Forensic Eye" in html

    # Sources endpoint
    src_resp = client.get("/api/visualizer/sources")
    assert src_resp.status_code == 200
    data = src_resp.get_json()
    assert isinstance(data.get("items"), list)
    assert any(i.get("name") == "smoke.txt" for i in data["items"])

    source_id = next(i["id"] for i in data["items"] if i.get("name") == "smoke.txt")

    # Render endpoint
    render_resp = client.get(f"/api/visualizer/render?source={source_id}")
    assert render_resp.status_code == 200
    payload = render_resp.get_json()
    assert payload["kind"] == "text"
    assert payload["file"]["name"] == "smoke.txt"


def test_visualizer_summary_note_and_export_smoke(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    _seed_user(app)
    client = app.test_client()
    _login(client)

    import app.web as web

    tenant_in = web.EINGANG / "kukanilea"
    tenant_in.mkdir(parents=True, exist_ok=True)
    doc = tenant_in / "summary.txt"
    doc.write_text("Umsatz 1000 EUR. Kosten 300 EUR. Gewinn 700 EUR.", encoding="utf-8")

    src_resp = client.get("/api/visualizer/sources")
    source_id = next(i["id"] for i in src_resp.get_json()["items"] if i.get("name") == "summary.txt")

    summary_resp = client.post(
        "/api/visualizer/summary",
        json={"source": source_id},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert summary_resp.status_code == 200
    summary_data = summary_resp.get_json()
    assert "summary" in summary_data
    assert summary_data["source"]["name"] == "summary.txt"

    note_resp = client.post(
        "/api/visualizer/note",
        json={"source": source_id, "summary": summary_data["summary"], "title": "T1"},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert note_resp.status_code == 200
    assert note_resp.get_json().get("ok") is True

    export_resp = client.post(
        "/api/visualizer/export-pdf",
        json={"source": source_id, "summary": summary_data["summary"]},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert export_resp.status_code == 200
    assert export_resp.headers.get("Content-Type", "").startswith("application/pdf")
