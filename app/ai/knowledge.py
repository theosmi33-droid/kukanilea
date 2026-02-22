from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context

from app.config import Config

# compatibility sentinels for tests that monkeypatch module attributes
chromadb = None  # compatibility for tests
ollama = None  # compatibility for tests

_LOCK = threading.Lock()
_COLLECTION_NAME = "kukanilea_entities"


def _is_ai_enabled() -> bool:
    try:
        from app.ai import is_enabled

        return bool(is_enabled())
    except Exception:
        return False


def _get_chromadb():
    if not _is_ai_enabled():
        return None
    try:
        import chromadb  # type: ignore

        return chromadb
    except Exception as exc:
        raise RuntimeError(
            "AI is enabled but chromadb is unavailable. Install with: "
            "pip install chromadb sentence-transformers ollama"
        ) from exc


def _get_ollama():
    if not _is_ai_enabled():
        return None
    try:
        import ollama  # type: ignore

        return ollama
    except Exception as exc:
        raise RuntimeError(
            "AI is enabled but ollama is unavailable. Install with: "
            "pip install chromadb sentence-transformers ollama"
        ) from exc


def _user_data_root() -> Path:
    if has_app_context():
        return Path(current_app.config["USER_DATA_ROOT"])
    return Path(Config.USER_DATA_ROOT)


def _chroma_dir() -> Path:
    root = _user_data_root() / "chroma"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fallback_db_path() -> Path:
    return _user_data_root() / "ai_knowledge.sqlite3"


def _fallback_connect() -> sqlite3.Connection:
    db = _fallback_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_entries(
          entity_type TEXT NOT NULL,
          entity_id INTEGER NOT NULL,
          text TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(entity_type, entity_id)
        )
        """
    )
    con.commit()
    return con


def init_chroma() -> None:
    """Initialize persistent Chroma collection if available.

    Falls Chroma nicht importierbar ist, wird ein SQLite-Fallback vorbereitet.
    """
    chromadb_mod = _get_chromadb()
    if chromadb_mod is None:
        con = _fallback_connect()
        con.close()
        return

    with _LOCK:
        client = chromadb_mod.PersistentClient(path=str(_chroma_dir()))
        client.get_or_create_collection(name=_COLLECTION_NAME)


def _stable_embedding(text: str, dim: int = 64) -> list[float]:
    data = hashlib.sha256((text or "").encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < dim:
        for b in data:
            values.append((float(b) / 255.0) * 2.0 - 1.0)
            if len(values) >= dim:
                break
        data = hashlib.sha256(data).digest()
    return values


def embed_text(text: str) -> list[float]:
    """Return embedding vector via Ollama; fallback to deterministic local vector."""
    txt = (text or "").strip()
    if not txt:
        return _stable_embedding("", dim=64)

    ollama_mod = _get_ollama()
    if ollama_mod is not None:
        model = "nomic-embed-text"
        if has_app_context():
            model = str(current_app.config.get("OLLAMA_EMBED_MODEL", model))
        try:
            # Python ollama package may expose embed() or embeddings().
            if hasattr(ollama_mod, "embed"):
                out = ollama_mod.embed(model=model, input=txt)
                vectors = out.get("embeddings") or out.get("embedding") or []
                if (
                    isinstance(vectors, list)
                    and vectors
                    and isinstance(vectors[0], list)
                ):
                    return [float(x) for x in vectors[0]]
                if (
                    isinstance(vectors, list)
                    and vectors
                    and isinstance(vectors[0], (int, float))
                ):
                    return [float(x) for x in vectors]
            if hasattr(ollama_mod, "embeddings"):
                out = ollama_mod.embeddings(model=model, prompt=txt)
                vec = out.get("embedding") or []
                if isinstance(vec, list) and vec:
                    return [float(x) for x in vec]
        except Exception:
            pass

    return _stable_embedding(txt)


def _chroma_collection():
    chromadb_mod = _get_chromadb()
    if chromadb_mod is None:
        return None
    client = chromadb_mod.PersistentClient(path=str(_chroma_dir()))
    return client.get_or_create_collection(name=_COLLECTION_NAME)


def store_entity(
    entity_type: str,
    entity_id: int,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Store or update an entity embedding in the local KB."""
    entity_type = (entity_type or "").strip().lower()
    if not entity_type or int(entity_id) <= 0:
        return

    doc_text = (text or "").strip()
    if not doc_text:
        return

    meta = dict(metadata or {})
    meta.setdefault("entity_type", entity_type)
    meta.setdefault("entity_id", int(entity_id))

    if _get_chromadb() is not None:
        try:
            col = _chroma_collection()
            if col is not None:
                vec = embed_text(doc_text)
                key = f"{entity_type}:{int(entity_id)}"
                col.upsert(
                    ids=[key],
                    documents=[doc_text],
                    metadatas=[meta],
                    embeddings=[vec],
                )
                return
        except Exception:
            # hard fallback below
            pass

    con = _fallback_connect()
    try:
        con.execute(
            """
            INSERT OR REPLACE INTO knowledge_entries(entity_type, entity_id, text, metadata_json, updated_at)
            VALUES (?,?,?,?,CURRENT_TIMESTAMP)
            """,
            (
                entity_type,
                int(entity_id),
                doc_text,
                json.dumps(meta, ensure_ascii=False),
            ),
        )
        con.commit()
    finally:
        con.close()


def find_similar(query: str, n: int = 5) -> list[dict[str, Any]]:
    """Find semantically similar entities from local KB."""
    q = (query or "").strip()
    if not q:
        return []

    limit = max(1, min(int(n), 50))

    if _get_chromadb() is not None:
        try:
            col = _chroma_collection()
            if col is not None:
                vec = embed_text(q)
                result = col.query(query_embeddings=[vec], n_results=limit)
                ids = (result.get("ids") or [[]])[0]
                docs = (result.get("documents") or [[]])[0]
                metas = (result.get("metadatas") or [[]])[0]
                dists = (result.get("distances") or [[]])[0]
                out: list[dict[str, Any]] = []
                for idx, item_id in enumerate(ids):
                    out.append(
                        {
                            "id": str(item_id),
                            "text": str(docs[idx]) if idx < len(docs) else "",
                            "metadata": metas[idx]
                            if idx < len(metas) and isinstance(metas[idx], dict)
                            else {},
                            "distance": float(dists[idx]) if idx < len(dists) else 0.0,
                        }
                    )
                return out
        except Exception:
            pass

    # SQLite fallback: token overlap scoring
    tokens = [t.lower() for t in q.split() if len(t) >= 2]
    if not tokens:
        tokens = [q.lower()]
    where = " OR ".join("LOWER(text) LIKE ?" for _ in tokens)
    params = [f"%{tok}%" for tok in tokens] + [limit * 4]

    con = _fallback_connect()
    try:
        rows = con.execute(
            f"""
            SELECT entity_type, entity_id, text, metadata_json
            FROM knowledge_entries
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        con.close()

    scored: list[dict[str, Any]] = []
    for row in rows:
        txt = str(row["text"] or "")
        lower_txt = txt.lower()
        overlap = sum(1 for tok in tokens if tok in lower_txt)
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except Exception:
            meta = {}
        scored.append(
            {
                "id": f"{row['entity_type']}:{int(row['entity_id'])}",
                "text": txt,
                "metadata": meta if isinstance(meta, dict) else {},
                "distance": float(1.0 / (1 + overlap)),
            }
        )

    scored.sort(key=lambda r: r.get("distance", 1.0))
    return scored[:limit]
