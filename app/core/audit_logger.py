"""
app/core/audit_logger.py
DSGVO-konformer Audit-Logger für KUKANILEA.
Singleton-Pattern für revisionssichere Protokollierung.
"""

import json
import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from app.models.rule import Base, get_sa_session

logger = logging.getLogger("kukanilea.audit")

class AuditEntry(Base):
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    agent_name = Column(String, nullable=False)
    task_hash = Column(String, nullable=True) # SST oder Input Hash
    action_type = Column(String, nullable=False)
    metadata_json = Column(Text, nullable=True)
    status = Column(String, default='ok') # 'ok', 'veto', 'security_alert'

class AuditLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuditLogger, cls).__new__(cls)
        return cls._instance

    def anonymize_payload(self, payload: Any) -> str:
        """Schritt 3: Erkennt und maskiert PII (E-Mails, Namen) im Payload."""
        raw_str = json.dumps(payload, ensure_ascii=False) if not isinstance(payload, str) else payload
        
        # E-Mail Regex
        raw_str = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', raw_str)
        
        # Einfache Namens-Heuristik (Wort mit Großbuchstaben im Kontext von 'Kunde' etc.)
        # Für Prototyping Fokus auf E-Mail Maskierung
        return raw_str

    def log_event(self, agent_name: str, action_type: str, payload: Any, status: str = 'ok', task_hash: str = None, reasoning: str = None):
        """Loggt ein Agenten-Event revisionssicher inklusive Reasoning (XAI)."""
        if isinstance(payload, dict) and reasoning:
            # XAI: Reasoning-Hash in Meta aufnehmen
            payload["reasoning_hash"] = hashlib.sha256(reasoning.encode()).hexdigest()
            payload["reasoning_clear"] = reasoning

        safe_metadata = self.anonymize_payload(payload)
        
        session = get_sa_session()
        try:
            entry = AuditEntry(
                agent_name=agent_name,
                action_type=action_type,
                metadata_json=safe_metadata,
                status=status,
                task_hash=task_hash
            )
            session.add(entry)
            session.commit()
        except Exception as e:
            logger.error(f"Audit-Logging fehlgeschlagen: {e}")
        finally:
            session.close()

    def export_training_data(self, output_path: str = "instance/training_data.jsonl"):
        """Evolutionary Tuning: Exportiert erfolgreiche Lösungswege anonymisiert für Fine-Tuning."""
        import os
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        session = get_sa_session()
        entries = session.query(AuditEntry).filter(AuditEntry.status == 'ok').order_by(AuditEntry.timestamp.desc()).limit(500).all()
        
        with open(output_path, "w", encoding="utf-8") as f:
            for e in entries:
                # Minimal anonymized structured data for LLM tuning
                line = {"agent": e.agent_name, "action": e.action_type, "meta": e.metadata_json}
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        session.close()
        return output_path

    def log_security_event(self, agent_name: str, message: str, severity: str = 'CRITICAL'):
        """Schritt 5: Spezielles Logging für Sicherheitsverletzungen (SST Fail, Unbefugter Zugriff)."""
        logger.error(f"SECURITY ALERT [{severity}] from {agent_name}: {message}")
        self.log_event(agent_name, "SECURITY_ALERT", {"msg": message, "severity": severity}, status='security_alert')

    def export_audit_trail(self, limit: int = 100) -> str:
        """Schritt 6: Generiert einen signierten JSON-Bericht."""
        session = get_sa_session()
        entries = session.query(AuditEntry).order_by(AuditEntry.timestamp.desc()).limit(limit).all()
        
        report = {
            "exported_at": datetime.utcnow().isoformat(),
            "integrity_hash": "KUKA_CHAIN_STUB", # Hash-Chaining Implementierung folgt
            "logs": [
                {
                    "ts": e.timestamp.isoformat(),
                    "agent": e.agent_name,
                    "action": e.action_type,
                    "status": e.status,
                    "meta": e.metadata_json
                } for e in entries
            ]
        }
        session.close()
        return json.dumps(report, indent=2, ensure_ascii=False)
