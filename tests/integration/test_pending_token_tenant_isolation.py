from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask import session

import app.web as web
from app import create_app


def _build_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    app.config["TESTING"] = True
    app.config["SESSION_COOKIE_SECURE"] = False
    with app.app_context():
        from app.auth import hash_password

        auth_db = app.extensions["auth_db"]
        now = datetime.now(UTC).isoformat()
        auth_db.upsert_tenant("tenant_a", "Tenant A", now)
        auth_db.upsert_tenant("tenant_b", "Tenant B", now)
        auth_db.upsert_user("alice", hash_password("alice"), now)
        auth_db.upsert_membership("alice", "tenant_a", "DEV", now)
    return app


def _seed_session(client, *, tenant_id: str = "tenant_a", user: str = "alice") -> None:
    with client.session_transaction() as sess:
        sess["user"] = user
        sess["role"] = "DEV"
        sess["tenant_id"] = tenant_id
        sess["csrf_token"] = "csrf-test-token"


def _pending_payload(
    tmp_path: Path,
    *,
    tenant_key: str = "tenant",
    tenant_value: str = "tenant_a",
    status: str = "READY",
) -> dict:
    fp = tmp_path / "doc.txt"
    fp.write_text("tenant scoped content", encoding="utf-8")
    payload = {
        "filename": "doc.txt",
        "path": str(fp),
        "status": status,
    }
    payload[tenant_key] = tenant_value
    return payload


def _patch_pending_read(monkeypatch: pytest.MonkeyPatch, payload: dict | None):
    def _read_pending(token: str):
        if token != "tok":
            return None
        if payload is None:
            return None
        return dict(payload)

    monkeypatch.setattr(web, "read_pending", _read_pending)


def test_pending_helper_allows_matching_tenant_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    payload = _pending_payload(tmp_path, tenant_key="tenant", tenant_value="tenant_a")
    _patch_pending_read(monkeypatch, payload)

    with app.test_request_context("/"):
        session["tenant_id"] = "tenant_a"
        pending = web._pending_for_current_tenant("tok")
        assert pending is not None
        assert pending["tenant"] == "tenant_a"


def test_pending_helper_allows_matching_tenant_id_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    payload = _pending_payload(tmp_path, tenant_key="tenant_id", tenant_value="tenant_a")
    _patch_pending_read(monkeypatch, payload)

    with app.test_request_context("/"):
        session["tenant_id"] = "tenant_a"
        pending = web._pending_for_current_tenant("tok")
        assert pending is not None
        assert pending["tenant_id"] == "tenant_a"


def test_pending_helper_allows_matching_tenant_suggested_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    payload = _pending_payload(tmp_path, tenant_key="tenant_suggested", tenant_value="tenant_a")
    _patch_pending_read(monkeypatch, payload)

    with app.test_request_context("/"):
        session["tenant_id"] = "tenant_a"
        pending = web._pending_for_current_tenant("tok")
        assert pending is not None
        assert pending["tenant_suggested"] == "tenant_a"


def test_pending_helper_rejects_cross_tenant_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    payload = _pending_payload(tmp_path, tenant_key="tenant", tenant_value="tenant_b")
    _patch_pending_read(monkeypatch, payload)

    with app.test_request_context("/"):
        session["tenant_id"] = "tenant_a"
        assert web._pending_for_current_tenant("tok") is None


def test_pending_helper_returns_none_for_unknown_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    payload = _pending_payload(tmp_path)
    _patch_pending_read(monkeypatch, payload)

    with app.test_request_context("/"):
        session["tenant_id"] = "tenant_a"
        assert web._pending_for_current_tenant("missing") is None


def test_review_delete_requires_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.post("/review/tok/delete", base_url="https://localhost")
    assert response.status_code == 302
    assert (response.headers.get("Location") or "") in {"/bootstrap", "/login?next=/review/tok/delete"}


def test_review_delete_blocks_cross_tenant_pending_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_session(client, tenant_id="tenant_a")

    payload = _pending_payload(tmp_path, tenant_key="tenant", tenant_value="tenant_b")
    _patch_pending_read(monkeypatch, payload)

    calls: list[str] = []

    monkeypatch.setattr(web, "delete_pending", lambda token: calls.append(token))

    response = client.post(
        "/review/tok/delete",
        headers={"X-CSRF-Token": "csrf-test-token"},
        base_url="https://localhost",
    )
    assert response.status_code == 404
    assert calls == []


def test_review_delete_allows_same_tenant_pending_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_session(client, tenant_id="tenant_a")

    payload = _pending_payload(tmp_path, tenant_key="tenant", tenant_value="tenant_a")
    _patch_pending_read(monkeypatch, payload)

    calls: list[str] = []

    monkeypatch.setattr(web, "delete_pending", lambda token: calls.append(token))

    response = client.post(
        "/review/tok/delete",
        headers={"X-CSRF-Token": "csrf-test-token"},
        base_url="https://localhost",
    )
    assert response.status_code == 302
    assert response.headers.get("Location", "").endswith("/")
    assert calls == ["tok"]


def test_file_preview_requires_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/file/tok", base_url="https://localhost")
    assert response.status_code == 302
    assert (response.headers.get("Location") or "") in {"/bootstrap", "/login?next=/file/tok"}


def test_file_preview_blocks_cross_tenant_pending_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_session(client, tenant_id="tenant_a")

    payload = _pending_payload(tmp_path, tenant_key="tenant_id", tenant_value="tenant_b")
    _patch_pending_read(monkeypatch, payload)

    monkeypatch.setattr(web, "_is_allowed_path", lambda _fp: True)

    response = client.get("/file/tok", base_url="https://localhost")
    assert response.status_code == 404


def test_file_preview_allows_same_tenant_pending_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_session(client, tenant_id="tenant_a")

    payload = _pending_payload(tmp_path, tenant_key="tenant_id", tenant_value="tenant_a")
    _patch_pending_read(monkeypatch, payload)

    monkeypatch.setattr(web, "_is_allowed_path", lambda _fp: True)

    response = client.get("/file/tok", base_url="https://localhost")
    assert response.status_code == 200
    assert b"tenant scoped content" in response.data


def test_review_route_requires_authentication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/review/tok/kdnr", base_url="https://localhost")
    assert response.status_code == 302
    assert (response.headers.get("Location") or "") in {"/bootstrap", "/login?next=/review/tok/kdnr"}


def test_review_route_hides_cross_tenant_pending_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_session(client, tenant_id="tenant_a")

    payload = _pending_payload(tmp_path, tenant_key="tenant_suggested", tenant_value="tenant_b", status="ANALYZING")
    _patch_pending_read(monkeypatch, payload)

    response = client.get("/review/tok/kdnr", base_url="https://localhost")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Nicht gefunden." in html
    assert "doc.txt" not in html


def test_review_route_shows_same_tenant_analyzing_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_session(client, tenant_id="tenant_a")

    payload = _pending_payload(tmp_path, tenant_key="tenant_suggested", tenant_value="tenant_a", status="ANALYZING")
    _patch_pending_read(monkeypatch, payload)

    response = client.get("/review/tok/kdnr", base_url="https://localhost")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Analyse läuft noch" in html
