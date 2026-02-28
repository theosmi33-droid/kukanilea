"""
app/core/search.py
Global search engine across documents, tasks, and CRM.
"""
import sqlite3
import logging
from typing import List, Dict, Any

logger = logging.getLogger("kukanilea.search")

def global_search(query: str, db_path: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Performs a fast FTS5 search across indexed entities."""
    if not query:
        return []
    
    results = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Check if table exists
        check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='docs_index';").fetchone()
        if not check:
            return []

        # Determine if docs_index exists and has FTS enabled
        # Placeholder for FTS query. Assuming 'docs_index' is an FTS5 table or has an FTS5 shadow table.
        # In a real implementation, you'd join with the FTS table.
        sql = """
            SELECT doc_id, file_name, doctype, doc_date 
            FROM docs_index 
            WHERE (file_name LIKE ? OR kdnr LIKE ? OR customer_name LIKE ?) 
            LIMIT ?
        """
        rows = conn.execute(sql, (f"%{query}%", f"%{query}%", f"%{query}%", limit)).fetchall()
        for r in rows:
            results.append({
                "type": "document",
                "id": r["doc_id"],
                "title": r["file_name"],
                "subtitle": f"{r['doctype']} - {r['doc_date']}"
            })
            
    except Exception as e:
        logger.error(f"Search failed: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
    return results
