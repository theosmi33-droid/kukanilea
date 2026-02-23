#!/usr/bin/env python3
"""
scripts/proactive_monitor.py
Das proaktive Nervensystem von KUKANILEA.
Scannt die DB nach Ereignissen und triggert AI-Agenten autonom.
"""

import os
import sys
import time
import logging
import json
import uuid
from pathlib import Path

# Projekt-Pfad hinzufügen
sys.path.append(str(Path(__file__).parent.parent))

from app.database import get_db_connection
from app.agents.orchestrator_v2 import delegate_task
from app.core.identity_parser import IdentityParser
from app.core.self_learning import propose_rule
from app.agents.procurement import MaterialProcurement
import asyncio

# Globaler Cache für verarbeitete IDs
PROCESSED_IDS = set()
logger = logging.getLogger("kukanilea.monitor")

def check_procurement(conn):
    """Prüft täglich anstehende Termine der nächsten 7 Tage und triggert Materialbestellung."""
    # Wir prüfen nur einmal täglich (oder alle 24h Loops)
    # Für Prototyp: Check alle 600 Loops (~5 Stunden)
    if int(time.time()) % 18000 < 35:
        logger.info("Starte täglichen Material-Check...")
        proc = MaterialProcurement()
        upcoming = proc.get_upcoming_appointments_needing_material(days=7)
        
        for item in upcoming:
            logger.info(f"Trigger Master Agent für Material-Disposition (Angebot #{item['quote_id']})")
            prompt = f"Bitte erstelle die Material-Bestellliste für Termin '{item['title']}' basierend auf Angebot #{item['quote_id']}."
            try:
                # Dispatcher Orchestrator V2 nutzen
                asyncio.run(delegate_task(prompt, tenant_id="SYSTEM_PROC"))
            except Exception as e:
                logger.error(f"Fehler bei Material-Disposition: {e}")

def check_self_learning(conn):
    """Prüft, ob neue Lektionen vorliegen und stößt ggf. Rule Proposals an."""
    # Wir prüfen nur alle 10 Loops (ca. 5 Minuten)
    if int(time.time()) % 300 < 35:
        logger.info("Starte Self-Learning Check...")
        try:
            # Da proactive_monitor synchron läuft, nutzen wir asyncio.run für den asynchronen call
            proposal_id = asyncio.run(propose_rule())
            if proposal_id:
                logger.info(f"Neuer Regelentwurf generiert: ID {proposal_id}")
        except Exception as e:
            logger.error(f"Fehler bei Self-Learning Check: {e}")

def check_new_receipts(conn):
    """Prüft auf neue OCR-Belege, die noch nicht verarbeitet wurden."""
    cursor = conn.execute("SELECT id, tenant_id, data_json FROM entities WHERE type='ocr_receipt' ORDER BY created_at DESC LIMIT 10")
    rows = cursor.fetchall()
    for row in rows:
        receipt_id = row['id']
        if receipt_id in PROCESSED_IDS:
            continue
            
        logger.info(f"Proaktiver Check: Neuer Beleg gefunden (ID: {receipt_id}). Triggere Orchestrator V2...")
        
        prompt = (
            f"Ich habe einen neuen Beleg im System gefunden (ID: {receipt_id}).\n"
            f"BELEG-DATEN: {row['data_json']}\n"
            "Prüfe den Beleg und buche ihn korrekt."
        )
        
        # Schritt 8: Dispatcher Orchestrator V2 nutzen
        try:
            result_text = asyncio.run(delegate_task(prompt, tenant_id=row['tenant_id']))
            
            # In Benachrichtigungs-Tabelle speichern
            conn.execute(
                "INSERT INTO agent_notifications (tenant_id, role, message) VALUES (?, ?, ?)",
                (row['tenant_id'], "CONTROLLER", result_text)
            )
            conn.commit()
            PROCESSED_IDS.add(receipt_id)
            logger.info(f"Benachrichtigung für {receipt_id} gespeichert.")
        except Exception as e:
            logger.error(f"Fehler bei Task-Delegation: {e}")

def monitor_loop():
    logger.info("KUKANILEA Proactive Monitor gestartet. Scanne System...")
    while True:
        try:
            conn = get_db_connection()
            check_new_receipts(conn)
            check_self_learning(conn)
            check_procurement(conn)
            conn.close()
        except Exception as e:
            logger.error(f"Fehler im Monitor: {e}")
        
        # Alle 30 Sekunden scannen
        time.sleep(30)

if __name__ == "__main__":
    monitor_loop()
