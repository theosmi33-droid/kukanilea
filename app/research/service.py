from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Any

from flask import current_app, session

from app.security.gates import confirm_gate


@dataclass(frozen=True)
class SourceRecord:
    title: str
    excerpt: str
    source: str
    fetched_at: str
    cached: bool = True
    url: str | None = None


class WebSearchConnector(Protocol):
    def search(self, query: str, *, topic: str, limit: int = 5) -> list[SourceRecord]:
        ...


class NullWebSearchConnector:
    """Default connector that performs no outbound requests."""

    def search(self, query: str, *, topic: str, limit: int = 5) -> list[SourceRecord]:
        return []


class CachedSourceStore:
    def __init__(self, cache_path: Path | None = None):
        self._cache_path = cache_path

    def load(self, *, topic: str, query: str, limit: int = 5) -> list[SourceRecord]:
        data = self._read_cache()
        scoped = [
            item
            for item in data
            if str(item.get("topic", "")).strip().lower() == topic.lower()
            and query.lower() in str(item.get("query", "")).strip().lower()
        ]
        if not scoped:
            scoped = [
                item
                for item in data
                if str(item.get("topic", "")).strip().lower() == topic.lower()
            ]
        records: list[SourceRecord] = []
        for raw in scoped[:limit]:
            records.append(
                SourceRecord(
                    title=str(raw.get("title") or "Untitled"),
                    excerpt=str(raw.get("excerpt") or ""),
                    source=str(raw.get("source") or "cache"),
                    fetched_at=str(raw.get("fetched_at") or _now_iso()),
                    cached=True,
                    url=str(raw.get("url")) if raw.get("url") else None,
                )
            )
        return records

    def _read_cache(self) -> list[dict[str, Any]]:
        if not self._cache_path or not self._cache_path.exists():
            return []
        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def summarize_from_sources(query: str, sources: list[SourceRecord], *, topic: str) -> str:
    if not sources:
        return f"No {topic} sources available for '{query}'."
    bullets = "\n".join(
        f"- {item.title}: {item.excerpt[:180]}" for item in sources
    )
    return f"{topic.title()} summary for '{query}':\n{bullets}"


def _resolve_connector() -> WebSearchConnector:
    return current_app.extensions.get("web_search_connector") or NullWebSearchConnector()


def _resolve_cache_store() -> CachedSourceStore:
    path = current_app.config.get("RESEARCH_CACHE_PATH")
    return current_app.extensions.get("research_cache_store") or CachedSourceStore(
        Path(path) if path else None
    )


def _resolve_core_db_path() -> str:
    session_db_path = session.get("tenant_db_path")
    if session_db_path:
        return str(session_db_path)

    try:
        from app.core import logic as core_logic

        db_path = getattr(core_logic, "DB_PATH", None)
        if db_path:
            return str(db_path)
    except Exception:
        pass

    return str(current_app.config["CORE_DB"])


def _store_summary_note(*, tenant_id: str, owner_user_id: str, title: str, body: str, metadata: dict[str, Any]) -> dict[str, Any]:
    note_id = f"sum-{uuid.uuid4().hex[:16]}"
    now = _now_iso()
    db_path = _resolve_core_db_path()
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_summary_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id TEXT UNIQUE NOT NULL,
                tenant_id TEXT NOT NULL,
                owner_user_id TEXT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            INSERT INTO ai_summary_notes(
                note_id, tenant_id, owner_user_id, title, body, metadata_json, created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (note_id, tenant_id, owner_user_id, title, body, json.dumps(metadata, ensure_ascii=False), now),
        )
    return {"note_id": note_id, "title": title, "created_at": now}


def generate_summary(*, topic: str, query: str, online: bool, confirm: str | None) -> dict[str, Any]:
    tenant_id = str(
        session.get("tenant_id") or current_app.config.get("TENANT_DEFAULT") or "KUKANILEA"
    )
    user = str(session.get("user") or "system")

    cache_store = _resolve_cache_store()
    connector = _resolve_connector()

    used_online = False
    outbound_blocked = False
    sources = cache_store.load(topic=topic, query=query, limit=5)

    if online:
        if not confirm_gate(confirm):
            outbound_blocked = True
        else:
            live = connector.search(query, topic=topic, limit=5)
            if live:
                sources = live
            used_online = True

    summary = summarize_from_sources(query, sources, topic=topic)
    provenance = {
        "schema_version": 1,
        "topic": topic,
        "query": query,
        "mode": "online" if used_online else "offline",
        "online_requested": bool(online),
        "outbound_blocked": outbound_blocked,
        "generated_at": _now_iso(),
        "sources": [
            {
                "title": s.title,
                "source": s.source,
                "excerpt": s.excerpt,
                "fetched_at": s.fetched_at,
                "cached": s.cached,
                "url": s.url,
            }
            for s in sources
        ],
    }

    note = _store_summary_note(
        tenant_id=tenant_id,
        owner_user_id=user,
        title=f"{topic.title()} summary: {query[:80]}",
        body=summary,
        metadata=provenance,
    )

    return {
        "ok": True,
        "topic": topic,
        "query": query,
        "summary": summary,
        "sources": provenance["sources"],
        "provenance": provenance,
        "note": note,
    }
