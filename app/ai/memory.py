"""
app/ai/memory.py
Local-Only Long-Term Memory (RAG) for KUKANILEA.
Uses sqlite-vec and sentence-transformers for semantic retrieval.
"""

import logging
import json
from typing import List, Any
from app.database import get_db_connection

logger = logging.getLogger("kukanilea.memory")

class LocalMemory:
    """Manages semantic memory using local embeddings and vector search."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy loader for the embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def store_memory(self, text: str, metadata: dict = None):
        """Generates embeddings and stores them in the vector table."""
        try:
            embedding = self.model.encode(text).tolist()
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Store metadata as JSON
            meta_json = json.dumps(metadata or {})
            
            # Note: The actual insert syntax for memory_vectors depends on sqlite-vec version
            # This is a conceptual implementation
            cursor.execute(
                "INSERT INTO memory_vectors(embedding) VALUES (?)",
                [json.dumps(embedding)]
            )
            conn.commit()
            conn.close()
            logger.info(f"Memory stored: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")

    def retrieve_context(self, query: str, top_k: int = 3) -> List[str]:
        """Retrieves semantically similar context from the memory."""
        try:
            query_embedding = self.model.encode(query).tolist()
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Vector search query using sqlite-vec functions
            cursor.execute("""
                SELECT rowid FROM memory_vectors 
                WHERE embedding MATCH ? 
                ORDER BY distance 
                LIMIT ?
            """, [json.dumps(query_embedding), top_k])
            
            # In a real implementation, we'd join with a text table to get the content
            results = cursor.fetchall()
            conn.close()
            return [str(r[0]) for r in results]
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return []

# Singleton instance
memory = LocalMemory()
