"""
app/services/price_service.py
Service für die lokale Preisdatenbank.
Nutzt FTS5 für die Artikelsuche und Preisfindung.
"""

import sqlite3
import logging
from typing import Optional, Dict, Any
from app.database import get_db_path, retry_on_lock

logger = logging.getLogger("kukanilea.price_service")

class PriceService:
    def __init__(self):
        self.db_path = get_db_path()

    @retry_on_lock()
    def get_price(self, description: str) -> Optional[Dict[str, Any]]:
        """
        Sucht einen Artikelpreis basierend auf der Beschreibung mittels FTS5.
        Gibt den passendsten Treffer zurück.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # FTS5 Ähnlichkeitssuche
            cursor = conn.execute(
                """
                SELECT article_number, description, unit_price, rank 
                FROM article_search 
                WHERE article_search MATCH ? 
                ORDER BY rank 
                LIMIT 1
                """,
                (f"{description}*",)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "article_number": row["article_number"],
                    "description": row["description"],
                    "unit_price": row["unit_price"],
                    "estimated": False
                }
            
            # Fallback: Einfache LIKE Suche falls FTS5 nichts findet
            cursor = conn.execute(
                "SELECT article_number, description, unit_price FROM prices WHERE description LIKE ? LIMIT 1",
                (f"%{description}%",)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "article_number": row["article_number"],
                    "description": row["description"],
                    "unit_price": row["unit_price"],
                    "estimated": False
                }
                
            return None
        except Exception as e:
            logger.error(f"Fehler bei Preissuche: {e}")
            return None
        finally:
            conn.close()

    def seed_initial_prices(self):
        """Beispiel-Daten für den Handwerker-Alltag."""
        initial_data = [
            ("ART-001", "Waschbecken Keramik Standard", 89.50),
            ("ART-002", "Einhandmischer Chrom", 45.00),
            ("ART-003", "Rohrbogen Kupfer 15mm", 2.45),
            ("ART-004", "Zement CEM II 25kg", 12.90),
            ("SRV-001", "Arbeitsstunde Sanitär", 65.00),
        ]
        conn = sqlite3.connect(self.db_path)
        try:
            for art_no, desc, price in initial_data:
                conn.execute(
                    "INSERT OR IGNORE INTO prices (article_number, description, unit_price) VALUES (?, ?, ?)",
                    (art_no, desc, price)
                )
            conn.commit()
        finally:
            conn.close()
