from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.config import Config


class OntologyRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _db_path(self) -> Path:
        if has_app_context():
            return Path(current_app.config["CORE_DB"])
        return Path(Config.CORE_DB)

    def _connect(self) -> sqlite3.Connection:
        db = self._db_path()
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db), timeout=30)
        con.row_factory = sqlite3.Row
        return con

    def ensure_schema(self) -> None:
        con = self._connect()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS ontology_types(
                  type_name TEXT PRIMARY KEY,
                  table_name TEXT NOT NULL,
                  pk_field TEXT NOT NULL DEFAULT 'id',
                  title_field TEXT,
                  description_field TEXT,
                  created_at TEXT
                )
                """
            )
            con.commit()
        finally:
            con.close()

    def register_type(
        self,
        type_name: str,
        table_name: str,
        pk_field: str = "id",
        title_field: str | None = None,
        description_field: str | None = None,
    ) -> None:
        self.ensure_schema()
        ts = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock:
            con = self._connect()
            try:
                con.execute(
                    """
                    INSERT OR REPLACE INTO ontology_types(
                      type_name, table_name, pk_field, title_field, description_field, created_at
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    (
                        (type_name or "").strip().lower(),
                        (table_name or "").strip(),
                        (pk_field or "id").strip(),
                        (title_field or "").strip() or None,
                        (description_field or "").strip() or None,
                        ts,
                    ),
                )
                con.commit()
            finally:
                con.close()

    def list_types(self) -> list[dict]:
        self.ensure_schema()
        con = self._connect()
        try:
            rows = con.execute(
                "SELECT * FROM ontology_types ORDER BY type_name"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()

    def _fetch_type(self, type_name: str) -> dict | None:
        self.ensure_schema()
        con = self._connect()
        try:
            row = con.execute(
                "SELECT * FROM ontology_types WHERE type_name=?",
                ((type_name or "").strip().lower(),),
            ).fetchone()
            return dict(row) if row else None
        finally:
            con.close()

    def get_entity(self, type_name: str, entity_id: int) -> dict[str, Any]:
        cfg = self._fetch_type(type_name)
        if not cfg:
            raise ValueError("unknown_type")

        tbl = cfg["table_name"]
        pk = cfg.get("pk_field") or "id"
        con = self._connect()
        try:
            row = con.execute(
                f"SELECT * FROM {tbl} WHERE {pk}=?",
                (int(entity_id),),
            ).fetchone()
            if not row:
                raise ValueError("entity_not_found")
            return dict(row)
        finally:
            con.close()

    def search_entities(
        self, type_name: str, query: str, limit: int = 20
    ) -> list[dict]:
        q = (query or "").strip()
        if not q:
            return []
        cfg = self._fetch_type(type_name)
        if not cfg:
            raise ValueError("unknown_type")

        tbl = cfg["table_name"]
        pk = cfg.get("pk_field") or "id"
        tf = cfg.get("title_field") or pk
        df = cfg.get("description_field") or ""

        fields = [tf]
        if df:
            fields.append(df)

        where = " OR ".join([f"LOWER(COALESCE({f}, '')) LIKE ?" for f in fields])
        params = [f"%{q.lower()}%" for _ in fields] + [max(1, min(int(limit), 200))]

        con = self._connect()
        try:
            rows = con.execute(
                f"""
                SELECT * FROM {tbl}
                WHERE {where}
                ORDER BY {pk} DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


_REGISTRY = OntologyRegistry()


def get_registry() -> OntologyRegistry:
    return _REGISTRY
