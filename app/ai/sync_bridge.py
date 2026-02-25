"""
ai_sync_bridge.py
Synchronisiert operative Daten mit der lokalen AI Knowledge Base.
Automatisiert den Wissenstransfer aus Kontakten, Tasks und Dokumenten.
"""
import sqlite3
import json
import sys
from pathlib import Path

# Pfade korrigieren
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from app.ai.knowledge import store_entity
from app.config import Config

def sync_all():
    print("[SYNC] Starte Abgleich: Operative DB -> AI Knowledge Base")
    db_path = Config.CORE_DB
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        # 1. Kontakte / Kunden synchronisieren
        rows = conn.execute("SELECT * FROM contacts").fetchall()
        for r in rows:
            text = f"Kunde/Kontakt: {r['name']} ({r['email']}). Zugeordnet zu Mandant {r['tenant_id']}."
            store_entity("contact", r['rowid'] if 'rowid' in r.keys() else 1, text, {"tenant": r['tenant_id']})
        
        # 2. Aufgaben synchronisieren
        rows = conn.execute("SELECT * FROM tasks").fetchall()
        for r in rows:
            text = f"Aufgabe: {r['title']}. Status: {r['status']}. Details: {r['details']}"
            store_entity("task", r['rowid'] if 'rowid' in r.keys() else 1, text, {"status": r['status']})
            
        # 3. Dokumente (OCR Content) synchronisieren
        rows = conn.execute("SELECT * FROM documents").fetchall()
        for r in rows:
            # Wir nehmen nur die ersten 2000 Zeichen für die semantische Suche
            content = (r['ocr_text'] or "")[:2000]
            if content:
                text = f"Dokument {r['id']}: {content}"
                store_entity("document", r['rowid'] if 'rowid' in r.keys() else 1, text, {"doc_id": r['id']})

        print("[SUCCESS] Live-Synchronisation abgeschlossen.")
    except Exception as e:
        print(f"[ERROR] Sync-Fehler: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    sync_all()
