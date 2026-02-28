from __future__ import annotations

import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.memory_refiner import calculate_importance
from app.agents.context_manager import ContextManager
from app.agents.memory_store import MemoryManager

def test_memory_intelligence():
    print("Testing KUKANILEA Memory Intelligence (v1.5)...")
    
    # 1. Test Importance Scoring (Mocked)
    mock_llm = MagicMock()
    mock_llm.complete.return_value = '{"score": 9, "category": "FAKT", "reason": "Enthält einen fixen Preis."}'
    
    score, cat = calculate_importance("Der Preis für das Kupferrohr ist 45 Euro.", llm_provider=mock_llm)
    print(f"Scored: {score}, Category: {cat}")
    assert score == 9
    assert cat == "FAKT"
    
    # 2. Test Context Pruning
    with tempfile.NamedTemporaryFile() as tmp:
        db_path = tmp.name
        # Setup table with importance
        con = sqlite3.connect(db_path)
        con.execute("""
            CREATE TABLE agent_memory(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              agent_role TEXT NOT NULL,
              content TEXT NOT NULL,
              embedding BLOB NOT NULL,
              metadata TEXT,
              importance_score INTEGER DEFAULT 5,
              category TEXT DEFAULT 'FAKT'
            );
        """)
        con.commit()
        con.close()
        
        # Patch MemoryManager to use our temp DB
        with patch("app.config.Config.AUTH_DB", Path(db_path)):
            # Mock embeddings
            with patch("app.agents.memory_store.generate_embedding", return_value=[0.1, 0.2]):
                manager = MemoryManager(db_path)
                manager.store_memory("T1", "agent", "Wichtige Info", importance_score=10, category="FAKT")
                manager.store_memory("T1", "agent", "Unwichtiger Smalltalk", importance_score=2, category="SMALLTALK")
                
                ctx = ContextManager("T1")
                # Retrieval should prioritize importance
                relevant = ctx.get_relevant_context("Info", limit=1, min_importance=5)
                print(f"Relevant context:\n{relevant}")
                
                assert "Wichtige Info" in relevant
                assert "Smalltalk" not in relevant

    print("Memory Intelligence Test: PASS")

if __name__ == "__main__":
    test_memory_intelligence()
