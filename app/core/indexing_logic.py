"""
app/core/indexing_logic.py
KUKANILEA v1.4 — Individual Intelligence Engine.
Integrates YAKE! for keyword extraction and SQLite fts5vocab for weighting.
"""

import sqlite3
import logging
import json
import yake
from pathlib import Path
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("kukanilea.intelligence")

class IndividualIntelligence:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        # Phase 3: YAKE Configuration (1-3 n-grams)
        self.kw_extractor = yake.KeywordExtractor(
            lan="german", 
            n=3, 
            dedupLim=0.9, 
            top=10, 
            features=None
        )

    def get_weighted_suggestions(self, text: str) -> List[str]:
        """
        Phase 3: Extracts keywords from text and weights them against 
        the frequency in the individual database (Phase 2).
        """
        if not text:
            return []

        # 1. Extract candidates from new document via YAKE
        candidates = self.kw_extractor.extract_keywords(text)
        candidate_words = [c[0].lower() for c in candidates]

        # 2. Get global frequencies from individual DB (Phase 2: fts5vocab)
        db_weights = self._get_db_vocabulary_weights()

        # 3. Combine: Candidates already frequent in DB move to the top
        weighted_list = []
        for word in candidate_words:
            # Score = 1.0 (YAKE) + DB Frequency Weight
            freq = db_weights.get(word, 0)
            weighted_list.append((word, freq))

        # Sort by frequency (descending)
        weighted_list.sort(key=lambda x: x[1], reverse=True)
        
        return [w[0] for w in weighted_list]

    def _get_db_vocabulary_weights(self) -> Dict[str, int]:
        """Phase 2: Analyzes term frequency using fts5vocab."""
        weights = {}
        if not self.db_path.exists():
            return weights

        try:
            conn = sqlite3.connect(str(self.db_path))
            # Ensure vocab table exists
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS vocab_index USING fts5vocab(docs_fts, row);")
            
            rows = conn.execute("SELECT term, cnt FROM vocab_index ORDER BY cnt DESC LIMIT 100").fetchall()
            for r in rows:
                weights[r[0].lower()] = r[1]
            conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch DB weights: {e}")
            
        return weights

    def optimize_index(self):
        """Phase 2: Nightly optimization task."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("INSERT INTO docs_fts(docs_fts) VALUES('optimize');")
            conn.commit()
            conn.close()
            logger.info("FTS Index optimized.")
        except Exception as e:
            logger.error(f"Index optimization failed: {e}")
