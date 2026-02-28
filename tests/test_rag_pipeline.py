from __future__ import annotations

import os
import sys
from unittest.mock import patch

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.rag_sync import chunk_text, sync_document_to_memory
from app.agents.search import SearchAgent
from app.agents.base import AgentContext

def test_rag_pipeline():
    print("Testing KUKANILEA RAG Pipeline...")
    
    # 1. Test Chunking
    text = "A" * 1000 + "B" * 1000
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    print(f"Generated {len(chunks)} chunks.")
    assert len(chunks) >= 3
    assert chunks[0].startswith("A" * 800)
    
    # 2. Test Hybrid Search Integration
    # We mock core and memory manager to test the logic flow
    mock_core = type("Core", (), {"assistant_search": lambda *args, **kwargs: []})()
    agent = SearchAgent(mock_core)
    
    # Mock context
    context = AgentContext(tenant_id="test_tenant", user="test_user", role="ADMIN")
    
    # Mock semantic hits
    mock_hits = [
        {
            "content": "Gefundener Inhalt aus dem Gedächtnis",
            "score": 0.95,
            "metadata": {
                "type": "document_snippet",
                "doc_id": "doc_123",
                "file_name": "rechnung_bau.pdf",
                "kdnr": "10001",
                "doctype": "RECHNUNG"
            }
        }
    ]
    
    with patch("app.agents.memory_store.MemoryManager.retrieve_context", return_value=mock_hits):
        results, suggestions = agent.search("bau rechnung", context)
        
        print(f"Search results: {results}")
        assert len(results) == 1
        assert "[Semantic Match]" in results[0]["file_name"]
        assert results[0]["doc_id"] == "doc_123"

    print("RAG Pipeline Test: PASS")

if __name__ == "__main__":
    test_rag_pipeline()
