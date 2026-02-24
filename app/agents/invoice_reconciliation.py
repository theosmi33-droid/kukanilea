"""
app/agents/invoice_reconciliation.py
Autonomer OCR-Rechnungsabgleich für KUKANILEA.
Vergleicht Lieferantenrechnungen mit Bestellungen und erkennt Abweichungen.
"""

import json
import logging
import secrets
from typing import Dict, List, Any, Optional
from app.database import get_db_connection

logger = logging.getLogger("kukanilea.invoice_reconciliation")

class InvoiceReconciliation:
    def __init__(self):
        pass

    def wrap_with_salt(self, content: str) -> str:
        """Sicherheit: Salted Tags gegen Injection in OCR-Textblöcken."""
        salt = secrets.token_hex(4)
        tag = f"KUKA_OCR_{salt}"
        return f"\\n<{tag}>\\n{content}\\n</{tag}>\\n"

    def verify_supplier_invoice(self, order_id: str, ocr_text: str) -> Dict[str, Any]:
        """
        Gleicht OCR-Daten mit einer Bestellung ab.
        Schritt 2: Implementierung des Prüfwerkzeugs.
        """
        # 1. SST auf OCR-Text anwenden (Schritt 6)
        safe_ocr = self.wrap_with_salt(ocr_text)
        
        # 2. Bestellung aus DB holen
        conn = get_db_connection()
        try:
            # Wir suchen in entities nach der Bestellung
            order = conn.execute(
                "SELECT data_json FROM entities WHERE id = ? AND type = 'material_order' LIMIT 1",
                (order_id,)
            ).fetchone()
            
            if not order:
                return {
                    "status": "clarification_needed",
                    "reason": f"Bestellung {order_id} nicht gefunden.",
                    "klaerfall": True
                }
            
            order_data = json.loads(order['data_json'])
            order_items = order_data.get('items', [])
            
            # 3. OCR Text analysieren (Simuliert oder via LLM)
            # In der echten Implementierung würde hier ein spezialisierter Controller-Prompt 
            # den OCR-Text gegen die Artikel-Liste prüfen.
            
            # Beispielhafte Logik für den Vergleich:
            invoice_total = 105.0  # Extrahiert aus OCR
            order_total = order_data.get('total_net', 100.0)
            
            deviation = (invoice_total / order_total) - 1.0
            
            comparison = {
                "order_id": order_id,
                "order_total": order_total,
                "invoice_total": invoice_total,
                "deviation_percent": round(deviation * 100, 2),
                "items_match": True, # Dummy
                "ocr_context": safe_ocr
            }
            
            # Schritt 4/5: Wenn Abweichung > 3%, als Klärfall markieren
            if abs(deviation) > 0.03:
                return {
                    "status": "discrepancy_detected",
                    "data": comparison,
                    "klaerfall": True,
                    "reason": f"Abweichung von {comparison['deviation_percent']}% übersteigt Limit (3%)."
                }
            
            return {
                "status": "verified",
                "data": comparison,
                "klaerfall": False
            }
            
        finally:
            conn.close()
