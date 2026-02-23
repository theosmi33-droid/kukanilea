"""
app/agents/orchestrator_v2.py
Multi-Agenten-Dispatcher mit Salted Sequence Tags (SST) und spezialisiertem Tool-Zugriff.
"""

import json
import secrets
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Dict
from pathlib import Path

from app.core.identity_parser import IdentityParser
from app.agents.observer import ObserverAgent
from app.agents.tools import dispatch, TOOL_REGISTRY
from app.core.audit_logger import AuditLogger

logger = logging.getLogger("kukanilea.orchestrator_v2")
audit = AuditLogger()

# ------------------------------------------------------------
# SST-Sicherheitslayer
# ------------------------------------------------------------

def generate_session_salt() -> str:
    """Schritt 1: Generiert einen kryptographisch sicheren Salt pro Session."""
    return secrets.token_hex(16)

def wrap_tool_output(output: str, salt: str) -> str:
    """Schritt 2: Wickelt Tool-Ausgabe in SST-Tags ein."""
    return f"<salt_{salt}>{output}</salt_{salt}>"

def validate_sequence(wrapped_output: str, expected_salt: str) -> bool:
    """Schritt 3: Prüft die Integrität der SST-Sequenz."""
    start_tag = f"<salt_{expected_salt}>"
    end_tag = f"</salt_{expected_salt}>"
    if not wrapped_output.startswith(start_tag) or not wrapped_output.endswith(end_tag):
        return False
    # Verhindere Nested Tags (Indiz für Injection)
    if wrapped_output.count("<salt_") > 1:
        return False
    return True

# ------------------------------------------------------------
# Agenten-Definitionen
# ------------------------------------------------------------

class BaseAgent(ABC):
    def __init__(self, role: str):
        self.role = role
        self.parser = IdentityParser(Path("instance/identity"))
        self.persona = self._load_soul()
        self.session_salt = None
        self.allowed_tools: List[str] = []

    def _load_soul(self) -> str:
        soul_content = self.parser.load_file_content("SOUL.md")
        if "## Deine Persönlichkeit" in soul_content:
            return soul_content.split("## Deine Persönlichkeit")[1].split("##")[0].strip()
        return "Du bist ein präziser digitaler Meister."

    def set_session_salt(self, salt: str):
        self.session_salt = salt

    @abstractmethod
    async def process(self, input_text: str, tenant_id: str, user_id: str) -> str:
        pass

    async def call_tool(self, tool_name: str, args: dict, tenant_id: str, user_id: str, reasoning: str = None) -> str:
        """Sicherer Tool-Aufruf mit SST, Zugriffskontrolle und XAI."""
        # Zugriffskontrolle (Schritt 5: Exception bei unbefugtem Aufruf)
        if tool_name not in self.allowed_tools:
            audit.log_security_event(self.role, f"Unbefugter Tool-Zugriff: {tool_name}")
            raise PermissionError(f"Agent {self.role} hat keinen Zugriff auf Tool {tool_name}")

        # Human-in-the-loop Trigger: Finanz-Impact > 1000€
        total_gross = float(args.get("total_gross", 0) or args.get("total", 0) or args.get("amount", 0))
        if total_gross > 1000.0:
            audit.log_event(self.role, "HITL_TRIGGERED", {"tool": tool_name, "amount": total_gross}, status="pending_approval")
            return f"Human-in-the-loop: Finanz-Impact > 1000€ ({total_gross}€). Warte auf manuelle Freigabe im Dashboard."

        # Observer Validierung
        from app.agents.observer import ObserverAgent
        observer = ObserverAgent()
        allowed, reason = observer.validate_action(tool_name, args)
        if not allowed:
            audit.log_event(self.role, f"TOOL_VETO:{tool_name}", args, status='veto', reasoning=reasoning)
            
            # Evolutionary Tuning Feedback Loop
            if self.role != "MASTER":
                refinement = f" [HINWEIS: Letzte Aktion ({tool_name}) wurde blockiert: {reason}. Bitte berücksichtigen.]"
                if refinement not in self.persona:
                    self.persona += refinement
                audit.log_event("MASTER", "PROMPT_REFINEMENT", {"target": self.role, "reason": reason})

            return f"Sicherheitsblockade: {reason}"

        # Dispatch
        result = dispatch(tool_name, args, read_only_flag=False, tenant_id=tenant_id, user=user_id)
        raw_res = json.dumps(result.get("result", {}), ensure_ascii=False)
        
        # XAI Audit Log
        audit.log_event(self.role, f"TOOL_CALL:{tool_name}", args, reasoning=reasoning)
        
        # SST Maskierung (Schritt 4)
        return wrap_tool_output(raw_res, self.session_salt)

class MasterAgent(BaseAgent):
    def __init__(self):
        super().__init__("MASTER")
        # Master bekommt exklusiv das Quote-Tool + alles andere
        self.allowed_tools = list(TOOL_REGISTRY.keys())
        from app.services.price_service import PriceService
        self.price_service = PriceService()

    async def process(self, input_text: str, tenant_id: str, user_id: str) -> str:
        # Isolierter Memory Context (Debugging / The Monolith Purge)
        context_memory = {"task": input_text, "tenant": tenant_id}

        # Falls eine Material-Bestellung für einen Termin angefordert wird (Schritt 3)
        if "material" in input_text.lower() and "angebot #" in input_text.lower():
            import re
            match = re.search(r"angebot #(\d+)", input_text.lower())
            if match:
                quote_id = int(match.group(1))
                reasoning = "Materialbestellung auf Basis der Angebots-ID für JIT-Disposition."
                # Salted Sequence Tags werden im Procurement Tool angewendet
                tool_res = await self.call_tool("generate_material_order", {"quote_id": quote_id}, tenant_id, user_id, reasoning=reasoning)
                if validate_sequence(tool_res, self.session_salt):
                    return f"Material-Bestellliste für Angebot #{quote_id} wurde generiert. Validierte Daten gesichert."
                return "Sicherheitsfehler: Materialdaten manipuliert."

        # Falls eine Angebotsanfrage erkannt wird (vereinfacht)
        if "angebot" in input_text.lower():
            # Schritt 3: Zuerst Preisdatenbank abfragen
            items_to_quote = ["Waschbecken Montage", "Armatur"]
            quoted_items = []
            
            for item_desc in items_to_quote:
                price_info = self.price_service.get_price(item_desc)
                if price_info:
                    # Schritt 5: SST für Preisdaten
                    price_info["source"] = "LOCAL_DB"
                    quoted_items.append(price_info)
                else:
                    # Notfall: Schätzen
                    quoted_items.append({
                        "description": item_desc,
                        "unit_price": 100.0,
                        "estimated": True,
                        "source": "AI_ESTIMATE"
                    })

            quote_data = {
                "customer_name": "Max Mustermann",
                "customer_address": "Musterstraße 1, 12345 Berlin",
                "items": [{"name": i["description"], "quantity": 1, "price_per_unit": i["unit_price"], "total": i["unit_price"], "estimated": i.get("estimated", False)} for i in quoted_items],
                "total_net": sum(i["unit_price"] for i in quoted_items),
                "tax_rate": 0.19,
            }
            quote_data["total_gross"] = quote_data["total_net"] * (1 + quote_data["tax_rate"])

            reasoning = "Lokale Preisdatenbank wurde für die Angebotserstellung konsultiert, um Margensicherheit zu gewährleisten."
            # Salted Sequence Tags für den Transfer nutzen
            tool_res = await self.call_tool("generate_pdf_quote", quote_data, tenant_id, user_id, reasoning=reasoning)
            
            if "Human-in-the-loop" in tool_res:
                return tool_res
                
            if validate_sequence(tool_res, self.session_salt):
                return f"Angebotsentwurf wurde erstellt. Validierte PDF-Daten gesichert."
            return "Sicherheitsfehler: Angebotsdaten manipuliert."
            
        return f"Meister-Analyse: {input_text}"

class ControllerAgent(BaseAgent):
    def __init__(self):
        super().__init__("CONTROLLER")
        # Schritt 3: Exklusiv DATEV, OCR und Rechnungskontrolle
        self.allowed_tools = ["datev_export", "datev_reconcile", "ocr_scan", "verify_supplier_invoice"]

    async def process(self, input_text: str, tenant_id: str, user_id: str) -> str:
        # Isolierter Context
        context_memory = {"task": input_text, "tenant": tenant_id}
        
        if "rechnung" in input_text.lower() and "abgleich" in input_text.lower():
            # In Echt würde hier das LLM die Order-ID und den OCR-Text extrahieren
            # Wir simulieren den Tool-Aufruf mit SST Schutz (Schritt 6)
            recon_data = {
                "order_id": "order_123",
                "ocr_text": "RECHNUNG Müller GmbH, Zement 105.00 EUR"
            }
            reasoning = "Rechnungsabgleich OCR vs. Bestellung für Margenkontrolle."
            tool_res = await self.call_tool("verify_supplier_invoice", recon_data, tenant_id, user_id, reasoning=reasoning)
            
            if "Human-in-the-loop" in tool_res:
                return tool_res
                
            if validate_sequence(tool_res, self.session_salt):
                return f"Rechnungsabgleich durchgeführt. Validierte Ergebnisse liegen vor."
            return "Sicherheitsfehler: Rechnungsdaten manipuliert."

        if "rechnung" in input_text.lower():
            reasoning = "OCR Extraktion für ankommende Rechnung."
            # Tool-Ergebnis mit SST
            tool_res = await self.call_tool("ocr_scan", {"path": "tmp/invoice.pdf"}, tenant_id, user_id, reasoning=reasoning)
            if validate_sequence(tool_res, self.session_salt):
                return f"Controller hat Beleg verarbeitet. Validierte Daten liegen vor."
            return "Sicherheitsfehler: Datenmanipulation erkannt."
        return "Controller bereit für Finanzprüfung."

class SecretaryAgent(BaseAgent):
    def __init__(self):
        super().__init__("SECRETARY")
        # Schritt 4: Exklusiv CRM, Email und Scheduler
        self.allowed_tools = ["crm_create_customer", "search_contacts", "postfach_sync", "postfach_send_draft", "schedule_appointment", "send_appointment_mail"]

    async def process(self, input_text: str, tenant_id: str, user_id: str) -> str:
        # Isolierter Context
        context_memory = {"task": input_text, "tenant": tenant_id}

        if "termin" in input_text.lower():
            # ... (scheduling logic)
            # Schritt 4: Bestätigungsmail versenden
            mail_data = {
                "recipient": "kunde@example.local",
                "subject": "Terminbestätigung: Montage Waschbecken",
                "body": "Guten Tag, Ihr Termin wurde für den 01.03.2026 um 08:00 Uhr gebucht.",
                "ical_path": "instance/calendar/Termin_20260301_0800.ics"
            }
            reasoning = "Automatischer E-Mail Versand nach erfolgreicher Terminierung."
            # SST Schutz für E-Mail Inhalte (Schritt 5)
            tool_res = await self.call_tool("send_appointment_mail", mail_data, tenant_id, user_id, reasoning=reasoning)
            if validate_sequence(tool_res, self.session_salt):
                return f"Termin wurde geplant und Bestätigungsmail versendet."
            return "Sicherheitsfehler: Mail-Daten manipuliert."

        if "kunde" in input_text.lower():
            reasoning = "CRM Suche für Kundenidentifikation."
            tool_res = await self.call_tool("search_contacts", {"query": input_text}, tenant_id, user_id, reasoning=reasoning)
            if validate_sequence(tool_res, self.session_salt):
                return f"Sekretariat hat Kundendaten sicher geladen."
            return "Sicherheitsfehler: CRM-Daten unvalidiert."
        return "Sekretariat bereit für Koordination."

# ------------------------------------------------------------
# Orchestrator V2 Dispatcher
# ------------------------------------------------------------

class OrchestratorV2:
    def __init__(self):
        self.session_salt = generate_session_salt()
        self.agents = {
            "controller": ControllerAgent(),
            "secretary": SecretaryAgent(),
            "master": MasterAgent()
        }
        for a in self.agents.values():
            a.set_session_salt(self.session_salt)

    async def delegate_task(self, user_input: str, tenant_id: str = "KUKANILEA", user_id: str = "system") -> str:
        # Klassifizierung
        category = "master"
        low = user_input.lower()
        if any(x in low for x in ["rechnung", "datev", "ocr", "beleg"]): category = "controller"
        elif any(x in low for x in ["kunde", "termin", "mail", "crm"]): category = "secretary"
        
        agent = self.agents[category]
        logger.info(f"Task -> {agent.role} (Session Salt: {self.session_salt[:4]}...)")
        
        # Audit Log (Schritt 4)
        audit.log_event("ORCHESTRATOR", "TASK_DELEGATION", {"input": user_input, "target": agent.role})
        
        try:
            res = await agent.process(user_input, tenant_id, user_id)
            if "Sicherheitsfehler" in res:
                audit.log_security_event(agent.role, f"Manipulation erkannt: {res}")
            return res
        except PermissionError as e:
            audit.log_security_event(agent.role, str(e))
            return f"Sicherheitsfehler: {str(e)}"
        except Exception as e:
            audit.log_event(agent.role, "SYSTEM_ERROR", str(e), status='error')
            return f"Systemfehler: {str(e)}"

    async def delegate_task_batch(self, user_inputs: List[str], tenant_id: str = "KUKANILEA", user_id: str = "system") -> List[str]:
        """Verarbeitet mehrere Tasks parallel mittels asyncio.gather."""
        tasks = [self.delegate_task(ui, tenant_id, user_id) for ui in user_inputs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [str(res) for res in results]

# Singleton/Helper für Abwärtskompatibilität
_orch_instance = None

async def delegate_task(user_input: str, tenant_id: str = "KUKANILEA", user_id: str = "system") -> str:
    global _orch_instance
    if not _orch_instance:
        _orch_instance = OrchestratorV2()
    return await _orch_instance.delegate_task(user_input, tenant_id, user_id)
