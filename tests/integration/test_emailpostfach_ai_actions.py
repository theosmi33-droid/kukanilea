from __future__ import annotations

from pathlib import Path

import pytest

from tests.time_utils import utc_now_iso


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
        auth_db.upsert_user("dev", hash_password("dev"), now)
        auth_db.upsert_membership("dev", "KUKANILEA", "DEV", now)

    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = "dev"
        sess["role"] = "DEV"
        sess["tenant_id"] = "KUKANILEA"
        sess["csrf_token"] = "csrf-test"
    return c


def test_email_draft_reply_flow(client, monkeypatch: pytest.MonkeyPatch):
    from app.modules.mail import ai_actions

    monkeypatch.setattr(
        ai_actions,
        "postfach_generate_local_ai_reply_draft",
        lambda *_args, **_kwargs: {"ok": True, "draft_id": "d-1", "thread_id": "t-1"},
    )
    monkeypatch.setattr(
        ai_actions,
        "postfach_get_draft",
        lambda *_args, **_kwargs: {
            "to_plain": "kunde@example.com",
            "subject_plain": "Re: Anfrage",
            "body_plain": "Danke für Ihre Nachricht.",
        },
    )

    resp = client.post(
        "/api/ai/execute",
        json={"skill": "email.draft_reply", "payload": {"thread_id": "t-1"}, "confirm": False},
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["result"]["draft"]["draft_id"] == "d-1"
    assert body["result"]["draft"]["send_allowed"] is False


def test_email_send_reply_requires_confirm(client, monkeypatch: pytest.MonkeyPatch):
    from app.modules.mail import ai_actions

    ai_actions._IDEMPOTENCY_RESULTS.clear()  # noqa: SLF001
    calls = {"count": 0}

    def _send(*_args, **_kwargs):
        calls["count"] += 1
        return {"ok": True, "thread_id": "t-1", "message_id": "m-1"}

    monkeypatch.setattr(ai_actions, "postfach_send_draft", _send)

    denied = client.post(
        "/api/ai/execute",
        json={
            "skill": "email.send_reply",
            "payload": {"draft_id": "d-1", "idempotency_key": "idem-1"},
            "confirm": False,
        },
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "confirm_required"

    allowed = client.post(
        "/api/ai/execute",
        json={
            "skill": "email.send_reply",
            "payload": {"draft_id": "d-1", "idempotency_key": "idem-1"},
            "confirm": True,
        },
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert allowed.status_code == 200
    assert allowed.get_json()["result"]["ok"] is True

    replay = client.post(
        "/api/ai/execute",
        json={
            "skill": "email.send_reply",
            "payload": {"draft_id": "d-1", "idempotency_key": "idem-1"},
            "confirm": True,
        },
        headers={"X-CSRF-Token": "csrf-test"},
    )
    assert replay.status_code == 200
    assert replay.get_json()["result"]["idempotent_replay"] is True
    assert calls["count"] == 1


def test_email_execute_enforces_session_tenant(client, monkeypatch: pytest.MonkeyPatch):
    from app.modules.mail import ai_actions

    seen: dict[str, str | None] = {"tenant_id": None}

    def _search(*_args, **kwargs):
        seen["tenant_id"] = kwargs.get("tenant_id")
        return []

    monkeypatch.setattr(ai_actions, "postfach_search_messages", _search)

    resp = client.post(
        "/api/ai/execute",
        json={
            "skill": "email.search",
            "payload": {"query": "angebot", "tenant_id": "VICTIM"},
            "confirm": False,
        },
        headers={"X-CSRF-Token": "csrf-test"},
    )

    assert resp.status_code == 200
    assert seen["tenant_id"] == "KUKANILEA"


@pytest.mark.parametrize("tenant_key", ["tenant_id", "tenant", "tenantId"])
def test_email_actions_api_enforces_session_tenant(client, monkeypatch: pytest.MonkeyPatch, tenant_key: str):
    from app.modules.mail import ai_actions

    seen: dict[str, str | None] = {"tenant_id": None}

    def _search(*_args, **kwargs):
        seen["tenant_id"] = kwargs.get("tenant_id")
        return []

    monkeypatch.setattr(ai_actions, "postfach_search_messages", _search)

    resp = client.post(
        "/api/email/actions/search",
        json={"query": "angebot", tenant_key: "VICTIM"},
    )

    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert seen["tenant_id"] == "KUKANILEA"
