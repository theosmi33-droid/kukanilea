"""
app/core/suggestion_engine.py
Dynamic, frequency-based suggestion engine for KUKANILEA v2.6.
Analyzes existing database entries to provide weighted keyword/label suggestions.
"""

import sqlite3
import logging
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("kukanilea.suggestions")

class SuggestionEngine:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def get_frequent_labels(self, limit: int = 10) -> Dict[str, List[str]]:
        """Analyzes docs_index for the most frequent doctypes, kdnr, and keywords."""
        suggestions = {
            "doctypes": [],
            "customer_names": [],
            "kdnr": []
        }
        
        if not self.db_path.exists():
            return suggestions

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            
            # Analyze Doctypes
            rows = conn.execute(
                "SELECT doctype, COUNT(*) as c FROM docs_index GROUP BY doctype ORDER BY c DESC LIMIT ?", 
                (limit,)
            ).fetchall()
            suggestions["doctypes"] = [r["doctype"] for r in rows if r["doctype"]]
            
            # Analyze Customer Names
            rows = conn.execute(
                "SELECT customer_name, COUNT(*) as c FROM docs_index GROUP BY customer_name ORDER BY c DESC LIMIT ?", 
                (limit,)
            ).fetchall()
            suggestions["customer_names"] = [r["customer_name"] for r in rows if r["customer_name"]]

            # Analyze KDNR
            rows = conn.execute(
                "SELECT kdnr, COUNT(*) as c FROM docs_index GROUP BY kdnr ORDER BY c DESC LIMIT ?", 
                (limit,)
            ).fetchall()
            suggestions["kdnr"] = [r["kdnr"] for r in rows if r["kdnr"]]

            conn.close()
        except Exception as e:
            logger.error(f"Suggestion analysis failed: {e}")
            
        return suggestions

    def analyze_keywords(self, limit: int = 20) -> List[str]:
        """Extracts most frequent words from snippets/filenames for tagging."""
        if not self.db_path.exists():
            return []
            
        try:
            conn = sqlite3.connect(str(self.db_path))
            rows = conn.execute("SELECT file_name, snippet FROM docs_index").fetchall()
            
            words = []
            stop_words = {"der", "die", "das", "und", "ein", "eine", "von", "zu", "mit", "für", "auf", "ist", "rechnung", "angebot"}
            
            for r in rows:
                text = f"{r[0]} {r[1]}".lower()
                # Simple tokenization
                tokens = [w for w in text.split() if len(w) > 3 and w not in stop_words]
                words.extend(tokens)
                
            most_common = [w[0] for w in Counter(words).most_common(limit)]
            conn.close()
            return most_common
        except Exception:
            return []
