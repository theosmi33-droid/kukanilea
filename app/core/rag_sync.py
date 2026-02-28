from __future__ import annotations

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.agents.memory_store import MemoryManager
from app.config import Config

logger = logging.getLogger("kukanilea.rag_sync")

class RAGSync:
    """
    KUKANILEA v1.5 — RAG-SYNC Engine.
    Synchronizes individual database facts and keywords into the AI's semantic memory.
    """
    def __init__(self, db_path: Path, memory_file: Path):
        self.db_path = db_path
        self.memory_file = memory_file

    def sync_tenant_intelligence(self, tenant_id: str):
        """
        Extracts high-level intelligence from the individual DB 
        and updates the semantic MEMORY.md.
        """
        logger.info(f"RAG-SYNC: Synchronizing intelligence for tenant {tenant_id}...")
        
        # 1. Fetch top weighted keywords from DB
        intelligence_data = self._extract_key_facts(tenant_id)
        
        # 2. Format for MEMORY.md
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"\n### [{now}] Intelligence Sync (Tenant: {tenant_id})\n"
            f"- **Dominante Schlagworte:** {', '.join(intelligence_data['keywords'])}\n"
            f"- **Top Kunden:** {', '.join(intelligence_data['top_customers'])}\n"
            f"- **Dokumenten-Volumen:** {intelligence_data['doc_count']} Belege archiviert.\n"
        )
        
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
            res = conn.execute("SELECT COUNT(*) FROM docs_index WHERE tenant_id = ?", (tenant_id,)).fetchone()
            facts["doc_count"] = res[0] if res else 0
            
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
                # Fallback: analyze file_name if vocab not available
                k_rows = conn.execute(
                    "SELECT file_name FROM docs_index WHERE tenant_id = ? LIMIT 20", (tenant_id,)
                ).fetchall()
                words = []
                for r in k_rows:
                    words.extend([w.lower() for w in r[0].replace("_", " ").replace(".", " ").split() if len(w) > 3])
                facts["keywords"] = [w[0] for w in Counter(words).most_common(5)]
                
            conn.close()
        except Exception as e:
            logger.error(f"RAG-SYNC: Fact extraction failed: {e}")
            
        return facts

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    Lightweight text chunking with overlap.
    Ensures semantic context is preserved across chunks.
    """
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        if end >= text_len:
            break
            
        start += (chunk_size - overlap)
        
    return chunks

def sync_document_to_memory(
    tenant_id: str, 
    doc_id: str, 
    file_name: str, 
    text: str, 
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Chunks the document text and stores it in the semantic memory (agent_memory).
    Enables RAG capabilities for uploaded documents.
    """
    if not text or len(text.strip()) < 10:
        return 0
        
    # 1. Initialize Memory Manager
    auth_db_path = str(Config.AUTH_DB)
    manager = MemoryManager(auth_db_path)
    
    # 2. Chunk text
    chunks = chunk_text(text)
    logger.info(f"Syncing document {file_name} ({doc_id}) to memory. Generated {len(chunks)} chunks.")
    
    # 3. Store each chunk
    stored_count = 0
    for i, chunk in enumerate(chunks):
        chunk_meta = (metadata or {}).copy()
        chunk_meta.update({
            "doc_id": doc_id,
            "file_name": file_name,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "type": "document_snippet"
        })
        
        success = manager.store_memory(
            tenant_id=tenant_id,
            agent_role="document_engine",
            content=chunk,
            metadata=chunk_meta
        )
        if success:
            stored_count += 1
            
    return stored_count

def learn_from_correction(
    tenant_id: str,
    file_name: str,
    text: str,
    original_suggestions: Dict[str, Any],
    final_answers: Dict[str, Any]
) -> bool:
    """
    Analyzes differences between AI suggestions and user corrections.
    Stores significant corrections in semantic memory to improve future extractions.
    """
    corrections = []
    
    # 1. Compare Doctype
    s_type = (original_suggestions.get("doctype_suggested") or "").upper()
    f_type = (final_answers.get("doctype") or "").upper()
    if f_type and s_type and f_type != s_type:
        corrections.append(f"Dokument '{file_name}' wurde als {s_type} erkannt, ist aber tatsächlich {f_type}.")
        
    # 2. Compare KDNR
    s_kdnr = str(original_suggestions.get("kdnr_suggested") or "")
    f_kdnr = str(final_answers.get("kdnr") or "")
    if f_kdnr and s_kdnr and f_kdnr != s_kdnr:
        corrections.append(f"Für Dokument '{file_name}' wurde KDNR {s_kdnr} vorgeschlagen, korrekt ist jedoch {f_kdnr}.")

    if not corrections:
        return False
        
    # 3. Store corrections in memory
    auth_db_path = str(Config.AUTH_DB)
    manager = MemoryManager(auth_db_path)
    
    combined_text = "\n".join(corrections)
    # Also include a snippet of the text for context
    context_snippet = text[:500] if text else ""
    memory_content = f"KORREKTUR-WISSEN:\n{combined_text}\n\nKontext-Auszug:\n{context_snippet}"
    
    logger.info(f"Auto-Learning: Storing {len(corrections)} corrections for {file_name}")
    
    return manager.store_memory(
        tenant_id=tenant_id,
        agent_role="learning_engine",
        content=memory_content,
        metadata={
            "type": "ocr_correction",
            "file_name": file_name,
            "corrections_count": len(corrections)
        }
    )
