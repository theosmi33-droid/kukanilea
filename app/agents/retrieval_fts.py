from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import current_app, has_app_context

from app.config import Config


def get_index_db_path() -> Path:
    if has_app_context():
        root = Path(current_app.config["USER_DATA_ROOT"])
    else:
        root = Path(Config.USER_DATA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root / "facts_index.sqlite3"


def _get_core_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["CORE_DB"])
    return Path(Config.CORE_DB)


def _get_auth_db_path() -> Path:
    if has_app_context():
        return Path(current_app.config["AUTH_DB"])
    return Path(Config.AUTH_DB)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def detect_fts5(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_probe USING fts5(content);"
        )
        conn.execute("DROP TABLE IF EXISTS __fts5_probe;")
        return True
    except sqlite3.OperationalError:
        return False


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO rag_meta(key, value) VALUES (?, ?)",
        (key, value),
    )


def _get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM rag_meta WHERE key=?", (key,)).fetchone()
    return str(row["value"]) if row else default


def ensure_schema(index_db_path: Optional[Path] = None) -> None:
    path = index_db_path or get_index_db_path()
    con = _connect(path)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_meta(
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_queue(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              kind TEXT NOT NULL,
              pk INTEGER NOT NULL,
              op TEXT NOT NULL,
              ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS facts_meta(
              kind TEXT NOT NULL,
              pk INTEGER NOT NULL,
              content TEXT NOT NULL,
              meta_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(kind, pk)
            )
            """
        )
        fts_on = detect_fts5(con)
        if fts_on:
            con.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
                USING fts5(kind UNINDEXED, pk UNINDEXED, content)
                """
            )
            _set_meta(con, "fts5", "1")
        else:
            _set_meta(con, "fts5", "0")
        con.commit()
    finally:
        con.close()


def _fts_enabled(conn: sqlite3.Connection) -> bool:
    return _get_meta(conn, "fts5", "0") == "1"


def _rowv(row: sqlite3.Row, key: str, default: Any = "") -> Any:
    return row[key] if key in row.keys() else default


def _build_task_fact(row: sqlite3.Row) -> Tuple[str, Dict[str, Any]]:
    text = (
        f"Task #{row['id']} {row['title']} | status={_rowv(row, 'status', '')} | "
        f"severity={_rowv(row, 'severity', '')} | details={_rowv(row, 'details', '')}"
    )
    return text, {"kind": "task", "pk": int(row["id"])}


def _build_time_project_fact(row: sqlite3.Row) -> Tuple[str, Dict[str, Any]]:
    text = f"Projekt #{row['id']} {_rowv(row, 'name', '')} | status={_rowv(row, 'status', '')}"
    return text, {"kind": "time_project", "pk": int(row["id"])}


def _build_time_entry_fact(row: sqlite3.Row) -> Tuple[str, Dict[str, Any]]:
    text = (
        f"Zeit #{row['id']} user={_rowv(row, 'user', '')} | start={_rowv(row, 'start_at', '')} | "
        f"dauer={_rowv(row, 'duration_seconds', 0)}s | note={_rowv(row, 'note', '')}"
    )
    return text, {"kind": "time_entry", "pk": int(row["id"])}


def _build_user_fact(row: sqlite3.Row) -> Tuple[str, Dict[str, Any]]:
    text = f"User {_rowv(row, 'username', '')}"
    return text, {"kind": "user", "pk": int(_rowv(row, "id", 0) or 0)}


def _upsert_fact(
    conn: sqlite3.Connection,
    *,
    kind: str,
    pk: int,
    content: str,
    meta: Dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT OR REPLACE INTO facts_meta(kind, pk, content, meta_json, updated_at)
        VALUES (?,?,?,?,?)
        """,
        (kind, int(pk), content, json.dumps(meta, ensure_ascii=False), now),
    )
    if _fts_enabled(conn):
        conn.execute("DELETE FROM facts_fts WHERE kind=? AND pk=?", (kind, int(pk)))
        conn.execute(
            "INSERT INTO facts_fts(kind, pk, content) VALUES (?,?,?)",
            (kind, int(pk), content),
        )


def _delete_fact(conn: sqlite3.Connection, *, kind: str, pk: int) -> None:
    conn.execute("DELETE FROM facts_meta WHERE kind=? AND pk=?", (kind, int(pk)))
    if _fts_enabled(conn):
        conn.execute("DELETE FROM facts_fts WHERE kind=? AND pk=?", (kind, int(pk)))


def _fetch_row_for_kind(
    kind: str, pk: int
) -> Optional[Tuple[str, Dict[str, Any], str, int]]:
    core_path = _get_core_db_path()
    auth_path = _get_auth_db_path()

    if kind in {"task", "time_project", "time_entry"} and core_path.exists():
        con = _connect(core_path)
        try:
            table_map = {
                "task": ("tasks", _build_task_fact),
                "time_project": ("time_projects", _build_time_project_fact),
                "time_entry": ("time_entries", _build_time_entry_fact),
            }
            table, builder = table_map[kind]
            if not _table_exists(con, table):
                return None
            row = con.execute(
                f"SELECT * FROM {table} WHERE id=?", (int(pk),)
            ).fetchone()
            if not row:
                return None
            content, meta = builder(row)
            return kind, meta, content, int(pk)
        finally:
            con.close()

    if kind == "user" and auth_path.exists():
        con = _connect(auth_path)
        try:
            if not _table_exists(con, "users"):
                return None
            row = con.execute(
                "SELECT rowid AS id, username FROM users WHERE rowid=?", (int(pk),)
            ).fetchone()
            if not row:
                return None
            content, meta = _build_user_fact(row)
            return kind, meta, content, int(pk)
        finally:
            con.close()

    return None


def _iter_all_source_facts() -> Iterable[Tuple[str, int, str, Dict[str, Any]]]:
    core_path = _get_core_db_path()
    auth_path = _get_auth_db_path()

    if core_path.exists():
        con = _connect(core_path)
        try:
            if _table_exists(con, "tasks"):
                for row in con.execute("SELECT * FROM tasks ORDER BY id"):
                    content, meta = _build_task_fact(row)
                    yield "task", int(row["id"]), content, meta
            if _table_exists(con, "time_projects"):
                for row in con.execute("SELECT * FROM time_projects ORDER BY id"):
                    content, meta = _build_time_project_fact(row)
                    yield "time_project", int(row["id"]), content, meta
            if _table_exists(con, "time_entries"):
                for row in con.execute("SELECT * FROM time_entries ORDER BY id"):
                    content, meta = _build_time_entry_fact(row)
                    yield "time_entry", int(row["id"]), content, meta
        finally:
            con.close()

    if auth_path.exists():
        con = _connect(auth_path)
        try:
            if _table_exists(con, "users"):
                for row in con.execute(
                    "SELECT rowid AS id, username FROM users ORDER BY rowid"
                ):
                    content, meta = _build_user_fact(row)
                    yield "user", int(row["id"]), content, meta
        finally:
            con.close()


def index_all() -> None:
    ensure_schema()
    idx = _connect(get_index_db_path())
    try:
        idx.execute("BEGIN IMMEDIATE")
        idx.execute("DELETE FROM facts_meta")
        if _fts_enabled(idx):
            idx.execute("DELETE FROM facts_fts")
        for kind, pk, content, meta in _iter_all_source_facts():
            _upsert_fact(idx, kind=kind, pk=pk, content=content, meta=meta)
        _set_meta(idx, "bootstrap_done", "1")
        idx.commit()
    finally:
        idx.close()


def enqueue(kind: str, pk: int, op: str) -> None:
    if op not in {"upsert", "delete"}:
        return
    ensure_schema()
    con = _connect(get_index_db_path())
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("DELETE FROM rag_queue WHERE kind=? AND pk=?", (kind, int(pk)))
        con.execute(
            "INSERT INTO rag_queue(kind, pk, op, ts) VALUES (?,?,?,CURRENT_TIMESTAMP)",
            (kind, int(pk), op),
        )
        con.commit()
    finally:
        con.close()


def _bootstrap_if_needed(conn: sqlite3.Connection) -> None:
    if _get_meta(conn, "bootstrap_done", "0") == "1":
        return
    conn.execute("DELETE FROM facts_meta")
    if _fts_enabled(conn):
        conn.execute("DELETE FROM facts_fts")
    for kind, pk, content, meta in _iter_all_source_facts():
        _upsert_fact(conn, kind=kind, pk=pk, content=content, meta=meta)
    _set_meta(conn, "bootstrap_done", "1")


def process_queue(limit: int = 200) -> int:
    ensure_schema()
    con = _connect(get_index_db_path())
    try:
        con.execute("BEGIN IMMEDIATE")
        _bootstrap_if_needed(con)
        rows = con.execute(
            "SELECT id, kind, pk, op FROM rag_queue ORDER BY id LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        if not rows:
            con.commit()
            return 0

        ids = []
        for row in rows:
            ids.append(int(row["id"]))
            kind = str(row["kind"])
            pk = int(row["pk"])
            op = str(row["op"])
            if op == "delete":
                _delete_fact(con, kind=kind, pk=pk)
                continue
            fact = _fetch_row_for_kind(kind, pk)
            if not fact:
                _delete_fact(con, kind=kind, pk=pk)
                continue
            fact_kind, meta, content, fact_pk = fact
            _upsert_fact(
                con,
                kind=fact_kind,
                pk=fact_pk,
                content=content,
                meta=meta,
            )

        placeholders = ",".join("?" for _ in ids)
        con.execute(f"DELETE FROM rag_queue WHERE id IN ({placeholders})", ids)
        con.commit()
        return len(ids)
    finally:
        con.close()


def _tokenize(query: str) -> List[str]:
    return [t.strip().lower() for t in query.split() if len(t.strip()) >= 2]


def search(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []

    ensure_schema()
    con = _connect(get_index_db_path())
    try:
        _bootstrap_if_needed(con)
        out: List[Dict[str, Any]] = []
        if _fts_enabled(con):
            terms = _tokenize(q)
            match_expr = " OR ".join(t.replace('"', "") for t in terms) or q
            rows = con.execute(
                """
                SELECT kind, pk, content, bm25(facts_fts) AS score
                FROM facts_fts
                WHERE facts_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (match_expr, max(1, int(limit))),
            ).fetchall()
            for row in rows:
                out.append(
                    {
                        "text": str(row["content"]),
                        "meta": {"kind": str(row["kind"]), "pk": int(row["pk"])},
                        "score": float(row["score"] or 0.0),
                    }
                )
            return out

        tokens = _tokenize(q)
        if not tokens:
            tokens = [q.lower()]
        where = " OR ".join("LOWER(content) LIKE ?" for _ in tokens)
        params = [f"%{t}%" for t in tokens] + [max(1, int(limit))]
        rows = con.execute(
            f"""
            SELECT kind, pk, content
            FROM facts_meta
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        for row in rows:
            out.append(
                {
                    "text": str(row["content"]),
                    "meta": {"kind": str(row["kind"]), "pk": int(row["pk"])},
                    "score": 0.0,
                }
            )
        return out
    finally:
        con.close()


def upsert_external_fact(
    kind: str, pk: int, content: str, meta: Dict[str, Any]
) -> None:
    """Upsert an external fact (e.g. archived document) into retrieval index."""
    if not kind or int(pk) <= 0:
        return
    ensure_schema()
    con = _connect(get_index_db_path())
    try:
        con.execute("BEGIN IMMEDIATE")
        _bootstrap_if_needed(con)
        safe_meta = dict(meta or {})
        safe_meta.setdefault("kind", str(kind))
        safe_meta.setdefault("pk", int(pk))
        _upsert_fact(
            con,
            kind=str(kind),
            pk=int(pk),
            content=str(content or "").strip() or f"{kind} #{int(pk)}",
            meta=safe_meta,
        )
        con.commit()
    finally:
        con.close()
