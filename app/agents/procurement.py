"""
app/agents/procurement.py
Autonomer Material-Einkäufer für KUKANILEA.
Generiert Bestelllisten basierend auf Angeboten und Terminen.
"""

import sqlite3
import logging
import json
import secrets
from pathlib import Path
from typing import Dict, List, Any, Optional
from app.database import get_db_path, retry_on_lock

logger = logging.getLogger("kukanilea.procurement")

class MaterialProcurement:
    def __init__(self):
        self.db_path = get_db_path()

    def wrap_with_salt(self, content: str) -> str:
        """Sicherheit: Salted Tags gegen Injection in Artikelbeschreibungen."""
        salt = secrets.token_hex(4)
        tag = f"KUKA_PROC_{salt}"
        return f"
<{tag}>
{content}
</{tag}>
"

    @retry_on_lock()
    def generate_material_order(self, quote_id: int) -> Dict[str, Any]:
        """
        Extrahiert benötigte Artikel aus einem Angebot und generiert eine Bestellliste.
        Schritt 2: Extraktion von Artikeldaten.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Wir simulieren hier den Zugriff auf eine (noch zu erstellende) Angebotstabelle
            # In der echten Implementierung würden wir 'entities' oder eine spezifische Tabelle nutzen.
            # Für diesen Task nehmen wir an, dass die Angebotsdaten in 'entities' als JSON vorliegen.
            cursor = conn.execute(
                "SELECT data_json FROM entities WHERE id = ? AND type = 'quote' LIMIT 1",
                (f"quote_{quote_id}",)
            )
            row = cursor.fetchone()
            if not row:
                # Fallback für Prototyping: Suche in einer hypothetischen quotes Tabelle
                try:
                    cursor = conn.execute("SELECT items_json FROM quotes WHERE id = ?", (quote_id,))
                    row = cursor.fetchone()
                    items = json.loads(row[0]) if row else []
                except:
                    items = []
            else:
                data = json.loads(row['data_json'])
                items = data.get('items', [])

            if not items:
                return {"status": "error", "reason": f"Keine Artikel für Angebot {quote_id} gefunden."}

            order_list = []
            for item in items:
                # Schritt 5: SST für Artikelbeschreibungen
                safe_desc = self.wrap_with_salt(item.get('name', 'Unbekannter Artikel'))
                order_list.append({
                    "article": safe_desc,
                    "quantity": item.get('quantity', 1),
                    "original_item": item.get('name') # Für den Observer Abgleich
                })

            return {
                "status": "success",
                "quote_id": quote_id,
                "order_items": order_list,
                "timestamp": secrets.token_hex(8) # Unique Order ID stub
            }
        except Exception as e:
            logger.error(f"Fehler bei Material-Disposition: {e}")
            return {"status": "error", "reason": str(e)}
        finally:
            conn.close()

    @retry_on_lock()
    def get_upcoming_appointments_needing_material(self, days: int = 7) -> List[Dict[str, Any]]:
        """Scannt anstehende Termine und findet verknüpfte Angebote."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Suche in appointments (erstellt im Scheduler Task)
            # Wir nehmen an, dass in der 'description' oder einem neuen Feld die Quote-ID steht
            cursor = conn.execute(
                "SELECT * FROM appointments WHERE start_time >= date('now') AND start_time <= date('now', '+7 days')"
            )
            apps = cursor.fetchall()
            needing_procurement = []
            for app in apps:
                # Heuristik: Finde Quote-ID in Beschreibung (z.B. "Angebot #123")
                import re
                match = re.search(r"Angebot #(\d+)", app['description'] or "")
                if match:
                    needing_procurement.append({
                        "appointment_id": app['id'],
                        "quote_id": int(match.group(1)),
                        "title": app['title']
                    })
            return needing_procurement
        finally:
            conn.close()
