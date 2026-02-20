from __future__ import annotations

import app.web as webmod
from app import create_app


def _login(client, role: str = "DEV", username: str = "dev") -> None:
    with client.session_transaction() as sess:
        sess["user"] = username
        sess["role"] = role
        sess["tenant_id"] = "KUKANILEA"


def _reset_job_trackers() -> None:
    with webmod._JOB_TRACKER_LOCK:
        for key in list(webmod._JOB_TRACKERS.keys()):
            webmod._JOB_TRACKERS[key] = {}


def test_api_status_requires_login() -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()

    res = client.get("/api/status")
    assert res.status_code == 401
    payload = res.get_json() or {}
    assert payload.get("ok") is False
    assert (payload.get("error_code") == "auth_required") or (
        (payload.get("error") or {}).get("code") == "auth_required"
    )


def test_api_status_reports_queue_and_running(monkeypatch) -> None:
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="DEV", username="status_dev")
    _reset_job_trackers()

    monkeypatch.setattr(
        webmod,
        "list_pending",
        lambda: [
            {"_token": "a", "status": "ANALYZING"},
            {"_token": "b", "status": "ERROR"},
            {"_token": "c", "status": "READY"},
        ],
    )
    monkeypatch.setattr(
        webmod,
        "_ocr_status_snapshot",
        lambda tenant_id: {
            "available": True,
            "pending": 2,
            "processing": 1,
            "failed_24h": 0,
            "last_event_at": "",
        },
    )
    webmod._job_tracker_start("index")

    res = client.get("/api/status")
    assert res.status_code == 200
    payload = res.get_json() or {}
    assert payload.get("ok") is True
    queue = payload.get("queue") or {}
    assert queue.get("total") == 3
    assert queue.get("analyzing") == 1
    assert queue.get("error") == 1
    assert queue.get("ready") == 1
    assert (payload.get("jobs") or {}).get("index", {}).get("state") == "running"
    assert int(payload.get("running_total") or 0) >= 2


def test_dev_test_llm_updates_tracker(monkeypatch) -> None:
    class _FakeLLM:
        name = "fake-llm"

        def rewrite_query(self, q: str):
            return {"intent": "search", "query": q}

    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY="test")
    client = app.test_client()
    _login(client, role="DEV", username="llm_dev")
    _reset_job_trackers()

    monkeypatch.setattr(webmod.ORCHESTRATOR, "llm", _FakeLLM(), raising=False)

    res = client.post("/api/dev/test-llm", json={"q": "rechnung 123"})
    assert res.status_code == 200
    payload = res.get_json() or {}
    assert payload.get("ok") is True

    stat = client.get("/api/status")
    assert stat.status_code == 200
    data = stat.get_json() or {}
    llm = (data.get("jobs") or {}).get("llm") or {}
    assert llm.get("state") == "idle"
    assert int(llm.get("runs") or 0) >= 1
    last_result = llm.get("last_result") or {}
    assert last_result.get("intent") == "search"
