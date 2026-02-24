"""
app/ai/monitoring.py
Hidden Dev Feature: AI-basierte Anomalie-Erkennung & Betrugsschutz.
Scannt Transaktionen und Logs auf betrügerische Handlungen oder "unsaubere" Arbeit.
"""

import logging
import json
from typing import Any
from app.ai_chat.engine import ask_local_ai

logger = logging.getLogger("kukanilea.monitoring")

def analyze_user_behavior(user_id: str, action: str, data: Any):
    """
    Analysiert Nutzeraktionen im Hintergrund. 
    Bei Verdacht auf Missbrauch wird ein Dev-Task erstellt.
    """
    # Prompt an den "Meister" für Sicherheits-Audit
    audit_prompt = (
        f"Analysiere auf kriminelle Absichten, Betrug oder illegale Daten-Manipulation: "
        f"Nutzer: {user_id}, Aktion: {action}, Daten: {json.dumps(data)}. "
        "Erlaubt: Abfrage interner Firmendaten für den Betrieb. "
        "Verboten: Hilfe bei Steuerhinterziehung, Diebstahl, Betrug oder System-Hacking. "
        "Antworte nur mit 'ALARM' + Grund, wenn kriminell/fraudulent, sonst 'OK'."
    )
    
    # Wir nutzen den lokalen Meister für den Audit
    analysis = ask_local_ai(audit_prompt, tenant_id="SYSTEM_AUDIT")
    
    if "ALARM" in analysis.upper():
        logger.critical(f"SICHERHEITS-ALARM für {user_id}: {analysis}")
        _create_dev_task(f"Sicherheits-Audit: {user_id}", analysis)

def _create_dev_task(title: str, description: str):
    """Erstellt einen versteckten Task für den Developer."""
    import uuid
    try:
        # Hier binden wir uns an das Task-System an
        # dummy implementation for now
        from app.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO entities (id, tenant_id, type, data_json) VALUES (?,?,?,?)",
            (f"dev_alert_{uuid.uuid4().hex[:12]}", "ADMIN_DEV", "DEV_TASK", json.dumps({"title": title, "desc": description}))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to create dev task: {e}")
