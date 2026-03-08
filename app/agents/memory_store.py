from __future__ import annotations

import json
import logging
import sqlite3
import struct
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.ai.embeddings import generate_embedding

logger = logging.getLogger("kukanilea.agents.memory_store")

class MemoryManager:
    """
    Manages semantic long-term memory for KUKANILEA agents.
    Uses SQLite for persistence and Python-based cosine similarity for search.
    Ensures 100% tenant isolation.
    """

    def __init__(self, auth_db_path: str):
        self.db_path = auth_db_path

    def _get_con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _parse_utc_timestamp(self, raw_value: str, *, fallback: datetime) -> datetime:
        ts_value = (raw_value or "").strip()
        if not ts_value:
            return fallback
        if ts_value.endswith("Z"):
            ts_value = ts_value[:-1]
            if not ts_value.endswith(("+00:00", "-00:00")):
                ts_value += "+00:00"
        try:
            parsed = datetime.fromisoformat(ts_value)
        except ValueError:
            return fallback
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _audit_memory_event(
        self,
        *,
        con: sqlite3.Connection,
        tenant_id: str,
        action: str,
        memory_id: str | int,
        actor: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_audit_log(
              id TEXT PRIMARY KEY,
              memory_id TEXT NOT NULL,
              tenant_id TEXT NOT NULL,
              action TEXT NOT NULL,
              actor TEXT NOT NULL,
              payload TEXT,
              created_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_audit_tenant_ts ON memory_audit_log(tenant_id, created_at)"
        )
        con.execute(
            """
            INSERT INTO memory_audit_log(id, memory_id, tenant_id, action, actor, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                str(memory_id),
                tenant_id,
                action,
                actor,
                json.dumps(payload or {}),
                self._utcnow(),
            ),
        )

    def _generate_embedding_safe(self, text: str) -> list[float]:
        try:
            embedding = generate_embedding(text)
        except Exception as exc:
            logger.warning("Embedding backend unavailable: %s", exc)
            return []
        if not embedding:
            return []
        try:
            return [float(v) for v in embedding]
        except Exception:
            return []

    def store_memory(
        self,
        tenant_id: str,
        agent_role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: int = 5,
        category: str = "FAKT"
    ):
        """
        Generates an embedding and stores the memory in the database.
        """
        embedding = self._generate_embedding_safe(content)
        degraded_embedding = False
        if not embedding:
            degraded_embedding = True
            embedding = [0.0]

        # Convert float list to binary BLOB (float32)
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        ts = self._utcnow()
        safe_metadata = dict(metadata or {})
        if degraded_embedding:
            safe_metadata["embedding_status"] = "degraded"
            safe_metadata["embedding_backend"] = "unavailable"
        meta_json = json.dumps(safe_metadata)

        con = self._get_con()
        try:
            cur = con.execute(
                """
                INSERT INTO agent_memory (tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, ts, agent_role, content, blob, meta_json, importance_score, category)
            )
            self._audit_memory_event(
                con=con,
                tenant_id=tenant_id,
                action="write",
                memory_id=cur.lastrowid,
                actor=agent_role,
                payload={"category": category},
            )
            con.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store memory in DB: {e}")
            return False
        finally:
            con.close()

    def retrieve_context(self, tenant_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves relevant semantic context for a query.
        Performs Cosine Similarity search on the client side (Python) over the tenant's memories.
        """
        query_vec = self._generate_embedding_safe(query)
        if not query_vec:
            return self._retrieve_recent_context(tenant_id=tenant_id, limit=limit)

        con = self._get_con()
        try:
            # Absolute Tenant Isolation: Only fetch memories for this tenant
            rows = con.execute(
                "SELECT content, agent_role, embedding, metadata, timestamp, importance_score, category FROM agent_memory WHERE tenant_id = ?",
                (tenant_id,)
            ).fetchall()

            results: List[Tuple[float, Dict[str, Any]]] = []
            for row in rows:
                blob = row["embedding"]
                # Unpack binary BLOB back to float list
                vec_len = len(blob) // 4 if blob else 0
                if not vec_len:
                    continue
                db_vec = struct.unpack(f"{vec_len}f", blob)

                score = self._cosine_similarity(query_vec, db_vec)
                results.append((score, {
                    "content": row["content"],
                    "role": row["agent_role"],
                    "metadata": json.loads(row["metadata"]),
                    "timestamp": row["timestamp"],
                    "importance_score": row["importance_score"],
                    "category": row["category"],
                    "score": score
                }))

            # Sort by score descending and return top K
            results.sort(key=lambda x: x[0], reverse=True)
            return [res[1] for res in results[:limit]]

        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return []
        finally:
            con.close()

    def _retrieve_recent_context(self, tenant_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        con = self._get_con()
        try:
            rows = con.execute(
                """
                SELECT content, agent_role, metadata, timestamp, importance_score, category
                FROM agent_memory
                WHERE tenant_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (tenant_id, max(int(limit or 1), 1)),
            ).fetchall()
            return [
                {
                    "content": row["content"],
                    "role": row["agent_role"],
                    "metadata": json.loads(row["metadata"]),
                    "timestamp": row["timestamp"],
                    "importance_score": row["importance_score"],
                    "category": row["category"],
                    "score": 0.0,
                }
                for row in rows
            ]
        except Exception as exc:
            logger.error("Failed fallback context retrieval: %s", exc)
            return []
        finally:
            con.close()

    def _cosine_similarity(self, v1: List[float] | Tuple[float, ...], v2: List[float] | Tuple[float, ...]) -> float:
        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(a * a for a in v2))
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    def store_messenger_message(
        self,
        *,
        tenant_id: str,
        provider: str,
        sender: str,
        recipient: str,
        content: str,
        external_id: str = "",
        attachments: Optional[List[Dict[str, Any]]] = None,
        crm_match: Optional[Dict[str, Any]] = None,
        direction: str = "inbound",
        status: str = "stored",
    ) -> bool:
        """
        Stores one messenger message envelope in semantic memory.
        This avoids schema migration in scoped work while preserving provider metadata.
        """
        message_id = external_id.strip() or f"local-{uuid.uuid4()}"
        attachment_count = len(attachments or [])
        payload = (
            f"[{provider}] {direction} {sender}->{recipient}: {content.strip()} "
            f"(attachments={attachment_count})"
        ).strip()
        metadata = {
            "type": "messenger_message",
            "provider": (provider or "internal").strip().lower(),
            "external_id": message_id,
            "from": sender,
            "to": recipient,
            "attachments": attachments or [],
            "crm_match": crm_match or {},
            "direction": direction,
            "status": status,
            "created_at": self._utcnow(),
        }
        return bool(
            self.store_memory(
                tenant_id=tenant_id,
                agent_role="messenger",
                content=payload,
                metadata=metadata,
                importance_score=6,
                category="MESSENGER_MESSAGE",
            )
        )

    def search_messenger_messages(
        self, tenant_id: str, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        hits = self.retrieve_context(tenant_id=tenant_id, query=query, limit=max(limit, 1) * 3)
        messages: List[Dict[str, Any]] = []
        for hit in hits:
            meta = hit.get("metadata") or {}
            if meta.get("type") != "messenger_message":
                continue
            messages.append(
                {
                    "provider": meta.get("provider", "internal"),
                    "external_id": meta.get("external_id", ""),
                    "from": meta.get("from", ""),
                    "to": meta.get("to", ""),
                    "direction": meta.get("direction", ""),
                    "status": meta.get("status", ""),
                    "content": hit.get("content", ""),
                    "score": float(hit.get("score", 0.0)),
                    "timestamp": meta.get("created_at", hit.get("timestamp", "")),
                    "attachments": meta.get("attachments", []),
                    "crm_match": meta.get("crm_match", {}),
                }
            )
            if len(messages) >= limit:
                break
        return messages

    def store_knowledge_memory(
        self,
        *,
        tenant_id: str,
        content: str,
        topic: str,
        memory_type: str,
        actor: str,
        confirm_write: bool,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: int = 6,
    ) -> Dict[str, Any]:
        if not confirm_write:
            return {
                "status": "pending_confirmation",
                "confirm_required": True,
                "reason": "memory_write_requires_confirmation",
            }

        safe_meta = dict(metadata or {})
        safe_meta.update({"topic": topic, "memory_type": memory_type})
        ok = self.store_memory(
            tenant_id=tenant_id,
            agent_role=actor,
            content=content,
            metadata=safe_meta,
            importance_score=importance_score,
            category="KNOWLEDGE_MEMORY",
        )
        return {
            "status": "stored" if ok else "degraded",
            "tenant": tenant_id,
            "topic": topic,
            "memory_type": memory_type,
        }

    def retrieve_by_topic(
        self,
        *,
        tenant_id: str,
        topic: str,
        limit: int = 5,
        recency_days: int = 60,
    ) -> List[Dict[str, Any]]:
        con = self._get_con()
        try:
            rows = con.execute(
                """
                SELECT id, content, agent_role, metadata, timestamp, importance_score, category
                FROM agent_memory
                WHERE tenant_id = ?
                  AND category = 'KNOWLEDGE_MEMORY'
                  AND lower(json_extract(metadata, '$.topic')) = lower(?)
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (tenant_id, topic, max(int(limit or 1) * 5, 5)),
            ).fetchall()
            now = datetime.now(timezone.utc)
            ranked: List[Tuple[float, Dict[str, Any]]] = []
            for row in rows:
                ts_raw = row["timestamp"] or ""
                ts = self._parse_utc_timestamp(ts_raw, fallback=now)
                age_days = max((now - ts).total_seconds() / 86400.0, 0.0)
                recency = max(0.0, 1.0 - (age_days / max(recency_days, 1)))
                score = (0.75 * recency) + 0.25
                ranked.append(
                    (
                        score,
                        {
                            "id": row["id"],
                            "content": row["content"],
                            "role": row["agent_role"],
                            "metadata": json.loads(row["metadata"] or "{}"),
                            "timestamp": ts_raw,
                            "importance_score": row["importance_score"],
                            "category": row["category"],
                            "score": score,
                        },
                    )
                )
            ranked.sort(key=lambda item: item[0], reverse=True)
            return [entry for _, entry in ranked[: max(int(limit or 1), 1)]]
        finally:
            con.close()

    def cleanup_knowledge_memory(self, *, days: int = 60, actor: str = "system_cleanup") -> int:
        con = self._get_con()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_iso = cutoff.isoformat()
            stale_rows = con.execute(
                """
                SELECT id, tenant_id
                FROM agent_memory
                WHERE category = 'KNOWLEDGE_MEMORY' AND timestamp < ?
                """,
                (cutoff_iso,),
            ).fetchall()
            for row in stale_rows:
                self._audit_memory_event(
                    con=con,
                    tenant_id=row["tenant_id"],
                    action="delete",
                    memory_id=row["id"],
                    actor=actor,
                    payload={"reason": "retention", "days": days},
                )
            con.execute(
                "DELETE FROM agent_memory WHERE category = 'KNOWLEDGE_MEMORY' AND timestamp < ?",
                (cutoff_iso,),
            )
            con.commit()
            return len(stale_rows)
        finally:
            con.close()
