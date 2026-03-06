from __future__ import annotations

import json
import sqlite3

from app import create_app
from app.research.service import SourceRecord


class StubConnector:
    def __init__(self, rows: list[SourceRecord]):
        self.rows = rows
        self.calls = 0

    def search(self, query: str, *, topic: str, limit: int = 5) -> list[SourceRecord]:
        self.calls += 1
        return self.rows[:limit]


def _bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    monkeypatch.setenv("KUKANILEA_RESEARCH_CACHE_PATH", str(tmp_path / "research_cache.json"))
    app = create_app()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "tester"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"
    return app, client


def _write_cache(path, rows):
    path.write_text(json.dumps(rows), encoding="utf-8")


def _latest_summary_note(core_db_path: str):
    con = sqlite3.connect(core_db_path)
    try:
        row = con.execute(
            "SELECT body, metadata_json FROM ai_summary_notes ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    if not row:
        return "", {}
    return str(row[0] or ""), json.loads(str(row[1] or "{}"))


def test_research_summary_offline_uses_cache_only(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)
    _write_cache(
        tmp_path / "research_cache.json",
        [
            {
                "topic": "research",
                "query": "local ai",
                "title": "Cached Research A",
                "excerpt": "Offline finding A",
                "source": "cache:local",
                "fetched_at": "2026-01-01T00:00:00Z",
            }
        ],
    )
    connector = StubConnector(
        [
            SourceRecord(
                title="Live Research",
                excerpt="Should not be used in offline mode",
                source="connector:test",
                fetched_at="2026-02-01T00:00:00Z",
                cached=False,
                url="https://example.invalid/research",
            )
        ]
    )
    app.extensions["web_search_connector"] = connector

    response = client.post("/api/research/summary", json={"query": "local ai", "online": False})

    assert response.status_code == 200
    body = response.get_json()
    assert body["provenance"]["mode"] == "offline"
    assert body["sources"][0]["title"] == "Cached Research A"
    assert connector.calls == 0

    note_body, metadata = _latest_summary_note(str(app.config["CORE_DB"]))
    assert "Cached Research A" in note_body
    assert metadata["topic"] == "research"


def test_research_summary_online_requires_confirm_gate(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)
    _write_cache(
        tmp_path / "research_cache.json",
        [
            {
                "topic": "research",
                "query": "safety",
                "title": "Cached Safety",
                "excerpt": "Fallback source",
                "source": "cache:local",
                "fetched_at": "2026-01-01T00:00:00Z",
            }
        ],
    )
    connector = StubConnector([])
    app.extensions["web_search_connector"] = connector

    response = client.post("/api/research/summary", json={"query": "safety", "online": True})

    assert response.status_code == 409
    body = response.get_json()
    assert body["error"] == "confirm_required"
    assert body["provenance"]["outbound_blocked"] is True
    assert connector.calls == 0


def test_news_summary_online_with_confirm_uses_connector(tmp_path, monkeypatch):
    app, client = _bootstrap(tmp_path, monkeypatch)
    _write_cache(tmp_path / "research_cache.json", [])
    connector = StubConnector(
        [
            SourceRecord(
                title="Live News A",
                excerpt="Breaking update from connector",
                source="connector:test",
                fetched_at="2026-02-01T00:00:00Z",
                cached=False,
                url="https://example.invalid/news",
            )
        ]
    )
    app.extensions["web_search_connector"] = connector

    response = client.post(
        "/api/news/summary",
        json={"query": "industry", "online": True, "confirm": "YES"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["topic"] == "news"
    assert body["provenance"]["mode"] == "online"
    assert body["sources"][0]["title"] == "Live News A"
    assert connector.calls == 1
