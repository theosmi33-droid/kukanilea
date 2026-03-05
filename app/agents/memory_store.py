from __future__ import annotations

import json
import logging
import sqlite3
import struct
import math
import uuid
from datetime import datetime, timezone
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
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            logger.warning("Rejected memory write without tenant context")
            return False

        embedding = generate_embedding(content)
        if not embedding:
            logger.error("Could not store memory: Embedding generation failed.")
            return False

        # Convert float list to binary BLOB (float32)
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        ts = datetime.now(timezone.utc).isoformat() + "Z"
        meta_json = json.dumps(metadata or {})

        con = self._get_con()
        try:
            con.execute(
                """
                INSERT INTO agent_memory (tenant_id, timestamp, agent_role, content, embedding, metadata, importance_score, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, ts, agent_role, content, blob, meta_json, importance_score, category)
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
        tenant_id = str(tenant_id or "").strip()
        if not tenant_id:
            logger.warning("Rejected memory read without tenant context")
            return []

        query_vec = generate_embedding(query)
        if not query_vec:
            return []

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
                vec_len = len(blob) // 4
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
            "created_at": datetime.now(timezone.utc).isoformat() + "Z",
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
