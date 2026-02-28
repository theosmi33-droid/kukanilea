from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agents.memory_store import MemoryManager
from app.config import Config

logger = logging.getLogger("kukanilea.agents.context_manager")

class ContextManager:
    """
    Handles context pruning and semantic retrieval for the Agent fleet.
    Ensures that the most relevant and important memories are injected into the context window.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.memory = MemoryManager(str(Config.AUTH_DB))

    def get_relevant_context(self, query: str, limit: int = 3, min_importance: int = 1) -> str:
        """
        Retrieves relevant memories, filters by importance, and formats them for the LLM.
        """
        try:
            hits = self.memory.retrieve_context(self.tenant_id, query, limit=10)
            
            # Filter and Sort
            filtered_hits = [
                h for h in hits 
                if h.get("importance_score", 5) >= min_importance
            ]
            
            # Sort by importance, then by score
            filtered_hits.sort(key=lambda x: (x.get("importance_score", 5), x.get("score", 0)), reverse=True)
            
            final_hits = filtered_hits[:limit]
            
            if not final_hits:
                return ""

            context_lines = ["Hier ist relevantes Vorwissen für diese Anfrage:"]
            for hit in final_hits:
                ts = hit.get("timestamp", "")[:10]
                category = hit.get("category", "INFO")
                content = hit.get("content", "")
                context_lines.append(f"[{ts}] ({category}): {content}")
                
            return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return ""

    def prune_context(self, memories: List[Dict[str, Any]], max_tokens: int = 1024) -> List[Dict[str, Any]]:
        """
        Simple heuristic pruning based on character count (1 token ~= 4 chars).
        In a real scenario, use a tokenizer.
        """
        current_chars = 0
        max_chars = max_tokens * 4
        pruned = []
        
        for m in sorted(memories, key=lambda x: x.get("importance_score", 5), reverse=True):
            content_len = len(m.get("content", ""))
            if current_chars + content_len < max_chars:
                pruned.append(m)
                current_chars += content_len
            else:
                break
                
        return pruned
