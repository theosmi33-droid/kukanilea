"""
app/core/rag_sync.py
KUKANILEA v1.5 — RAG-SYNC Engine.
Synchronizes individual database facts and keywords into the AI's semantic memory.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("kukanilea.rag")

class RAGSync:
    def __init__(self, db_path: Path, memory_file: Path):
        self.db_path = db_path
        self.memory_file = memory_file

    def sync_tenant_intelligence(self, tenant_id: str):
        """
        Extracts high-level intelligence from the individual DB 
        and updates the semantic MEMORY.md.
        """
        logger.info(f"RAG-SYNC: Synchronizing intelligence for tenant {tenant_id}...")
        
        # 1. Fetch top weighted keywords from DB (from v1.4 IndividualIntelligence)
        intelligence_data = self._extract_key_facts(tenant_id)
        
        # 2. Format for MEMORY.md
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"
### [{now}] Intelligence Sync (Tenant: {tenant_id})
"
        entry += f"- **Dominante Schlagworte:** {', '.join(intelligence_data['keywords'])}
"
        entry += f"- **Top Kunden:** {', '.join(intelligence_data['top_customers'])}
"
        entry += f"- **Dokumenten-Volumen:** {intelligence_data['doc_count']} Belege archiviert.
"
        
        # 3. Append to MEMORY.md (Local-First Long-term Memory)
        try:
            with open(self.memory_file, "a", encoding="utf-8") as f:
                f.write(entry)
            logger.info("RAG-SYNC: Semantic memory updated.")
        except Exception as e:
            logger.error(f"RAG-SYNC: Memory write failed: {e}")

    def _extract_key_facts(self, tenant_id: str) -> Dict[str, Any]:
        """Queries the individual DB for core facts."""
        facts = {"keywords": [], "top_customers": [], "doc_count": 0}
        
        if not self.db_path.exists():
            return facts

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            
            # Count
            facts["doc_count"] = conn.execute("SELECT COUNT(*) FROM docs_index WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
            
            # Top Customers
            rows = conn.execute(
                "SELECT customer_name, COUNT(*) as c FROM docs_index WHERE tenant_id = ? GROUP BY customer_name ORDER BY c DESC LIMIT 5",
                (tenant_id,)
            ).fetchall()
            facts["top_customers"] = [r["customer_name"] for r in rows]
            
            # Top Keywords (weighted via vocab if available)
            try:
                k_rows = conn.execute(
                    "SELECT term FROM vocab_index ORDER BY cnt DESC LIMIT 10"
                ).fetchall()
                facts["keywords"] = [r["term"] for r in k_rows]
            except:
                pass # vocab_index might not be ready yet
                
            conn.close()
        except Exception as e:
            logger.error(f"RAG-SYNC: Fact extraction failed: {e}")
            
        return facts
