import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger("kukanilea.widget_db")

class WidgetDatabase:
    """
    Lightweight SQLite Database for the Floating Widget (LLMFit).
    Enforces a strict 60-day data retention policy (Auto-Cleanup).
    """
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes tables if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_prompt TEXT NOT NULL,
                    llm_response TEXT NOT NULL,
                    model_used TEXT,
                    is_flagged BOOLEAN DEFAULT 0
                )
            ''')
            conn.commit()

    def record_interaction(self, prompt: str, response: str, model: str, flagged: bool = False):
        """Records a new interaction in the local widget DB."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO interactions (user_prompt, llm_response, model_used, is_flagged) VALUES (?, ?, ?, ?)",
                (prompt, response, model, flagged)
            )
            conn.commit()

    def enforce_retention_policy(self, days: int = 60):
        """
        Auto-Cleanup Rule: Deletes all interactions older than `days`.
        Must be called on widget startup.
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM interactions WHERE timestamp < ?", (cutoff_date,))
                deleted_rows = cursor.rowcount
                conn.commit()
                # VACUUM to actually reclaim disk space
                conn.execute("VACUUM")
            if deleted_rows > 0:
                logger.info(f"Auto-Cleanup executed: {deleted_rows} old interactions removed.")
        except Exception as e:
            logger.error(f"Failed to enforce retention policy: {e}")

    def get_recent_history(self, limit: int = 50):
        """Retrieves context for the LLM."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM interactions ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows][::-1] # Reverse to chronological order
