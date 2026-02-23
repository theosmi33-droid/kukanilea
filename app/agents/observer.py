"""
app/agents/observer.py
Der Wachhund-Agent für KUKANILEA (Hybrid Gatekeeper).
Prüft geplante Aktionen gegen BOUNDARIES.md mit Salted Tags und LLM-Validierung.
"""

import json
import time
import secrets
import concurrent.futures
from pathlib import Path
from app.core.identity_parser import IdentityParser
from app.core.self_learning import log_correction

class ObserverAgent:
    def __init__(self):
        self.parser = IdentityParser(Path("instance/identity"))

    def wrap_with_salt(self, content: str) -> str:
        """Wickelt Content in Salted Tags ein, um Injection zu verhindern."""
        salt = secrets.token_hex(4)
        tag = f"KUKA_BOUNDS_{salt}"
        return f"\n<{tag}>\n{content}\n</{tag}>\n"

    def validate_action(self, action_name: str, args: dict) -> tuple[bool, str]:
        """
        Validiert eine geplante Aktion gegen die Sicherheitsgrenzen.
        Gibt (True, "") zurück wenn ok, sonst (False, "Grund").
        """
        # 1. Statische Python-Prüfung (Hybrid Observer) - Schnell & Sicher
        static_ok, static_reason = self._static_check(action_name, args)
        if not static_ok:
            self._log_veto(action_name, args, static_reason)
            return False, static_reason

        # 2. LLM-Prüfung mit Salted Boundaries & Timeout
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._llm_check, action_name, args)
                # Schritt 7: 3 Sekunden Timeout Fallback
                llm_ok, llm_reason = future.result(timeout=3.0)
                
                if not llm_ok:
                    self._log_veto(action_name, args, llm_reason)
                    return False, llm_reason
        except concurrent.futures.TimeoutError:
            reason = "Veto: LLM-Timeout (3s). Aktion blockiert (Fail Safe)."
            self._log_veto(action_name, args, reason)
            return False, reason
        except Exception as e:
            reason = f"Veto: Observer-Fehler ({str(e)}). Aktion blockiert."
            self._log_veto(action_name, args, reason)
            return False, reason

        return True, ""

    def _static_check(self, action_name: str, args: dict) -> tuple[bool, str]:
        """Harte statische Grenzen ohne LLM-Overhead."""
        # 1. Budget für Bestellungen (500€)
        if action_name == "order_material" or "total" in args:
            total = float(args.get("total", 0))
            if total > 500.0 and action_name != "generate_pdf_quote":
                return False, f"Statische Grenze: Budget von 500€ überschritten ({total}€)."
        
        # 2. Spezial-Check für Angebote (5000€ Limit + Unbekannte Artikel + Geschätzte Preise)
        if action_name == "generate_pdf_quote":
            total_gross = float(args.get("total_gross", 0))
            if total_gross > 5000.0:
                return False, f"Angebots-Veto: Summe {total_gross}€ > 5000€. Manuelle Freigabe erforderlich."
            
            # Check auf unbekannte Artikel oder geschätzte Preise (Schritt 4)
            for item in args.get("items", []):
                if not item.get("name") or "unbekannt" in item.get("name", "").lower():
                    return False, "Angebots-Veto: Enthält unbekannte Positionen. Human-in-the-loop nötig."
                
                if item.get("estimated"):
                    return False, f"Angebots-Veto: Preis für '{item.get('name')}' wurde geschätzt. Datenbank-Abgleich fehlgeschlagen."

        # 3. Schritt 5: Spezial-Check für Termine (Keine Überschneidung, 30 Min Puffer)
        if action_name == "schedule_appointment":
            # Die Scheduler-Klasse führt den Check bereits intern durch, 
            # aber der Observer muss es laut Mandat unerbittlich validieren.
            from app.database import get_db_path
            import sqlite3
            from datetime import datetime, timedelta
            
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            try:
                # Wir simulieren hier die Logik für den Observer
                start_str = args.get("start") or datetime.now().isoformat()
                start = datetime.fromisoformat(start_str)
                duration = timedelta(minutes=args.get("duration_minutes", 60))
                end = start + duration
                buffer = timedelta(minutes=30)
                
                slot_start = start - buffer
                slot_end = end + buffer
                
                cursor = conn.execute(
                    "SELECT title FROM appointments WHERE NOT (end_time <= ? OR start_time >= ?)",
                    (slot_start.isoformat(), slot_end.isoformat())
                )
                conflict = cursor.fetchone()
                if conflict:
                    return False, f"Termin-Veto: Überschneidung mit '{conflict[0]}' (inkl. 30 Min Fahrpuffer)."
            finally:
                conn.close()

        # 4. Schritt 4: Spezial-Check für Material-Disposition (Abgleich mit Angebot)
        if action_name == "generate_material_order":
            quote_id = args.get("quote_id")
            from app.database import get_db_path
            import sqlite3
            import json
            
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            try:
                # Hole Original-Artikel aus dem Angebot
                cursor = conn.execute(
                    "SELECT data_json FROM entities WHERE id = ? AND type = 'quote' LIMIT 1",
                    (f"quote_{quote_id}",)
                )
                row = cursor.fetchone()
                if not row:
                    return False, f"Procurement-Veto: Original-Angebot #{quote_id} nicht gefunden."
                
                original_data = json.loads(row[0])
                original_items = {item['name'] for item in original_data.get('items', [])}
                
                # Wir müssen hier den Result-Check simulieren, da der Tool-Call erst noch kommt
                # In der V2 Architektur validiert der Observer den TOOL_CALL Request.
                # Da wir hier nur die ID prüfen können, lassen wir es vorerst durch, 
                # sofern die ID valide ist. Ein tieferer Check müsste den Output validieren.
                if not original_items:
                    return False, f"Procurement-Veto: Angebot #{quote_id} enthält keine Artikel."
            finally:
                conn.close()

        # 5. Schritt 4: Spezial-Check für Rechnungskontrolle (Abweichung > 3%)
        if action_name == "verify_supplier_invoice":
            # Statischer Check auf IDs
            if not args.get("order_id") or not args.get("ocr_text"):
                return False, "Rechnungs-Veto: Unvollständige Daten für Abgleich."

        # Dynamischer Check für DB-Mutationen (Schritt 4/5)
        if action_name == "db_mutation" and args.get("table") == "entities":
            import json
            try:
                data = json.loads(args.get("data", "{}"))
                if data.get("type") == "supplier_invoice":
                    deviation = float(data.get("deviation_percent", 0))
                    if abs(deviation) > 3.0:
                        return False, f"Rechnungs-Veto: Abweichung {deviation}% > 3.0%. Klärfall generiert."
            except:
                pass

        if action_name == "delete_entity":
            # Nur MASTER darf löschen (vereinfacht für Prototyp)
            return False, "Statische Grenze: Direktes Löschen untersagt."
            
        return True, ""

    def _llm_check(self, action_name: str, args: dict) -> tuple[bool, str]:
        """Komplexe Prüfung gegen BOUNDARIES.md via LLM."""
        from app.agents.orchestrator import answer as agent_answer
        
        boundaries_raw = self.parser.load_file_content("BOUNDARIES.md")
        # Schritt 2: Salted Sequence Tags anwenden
        salted_bounds = self.wrap_with_salt(boundaries_raw)
        
        prompt = (
            "Du bist der KUKANILEA Observer. Deine einzige Aufgabe ist es, Aktionen gegen die Sicherheitsgrenzen zu prüfen. "
            f"GRENZEN:{salted_bounds}\n\n"
            f"GEPLANTE AKTION: {action_name}\n"
            f"PARAMETER: {json.dumps(args)}\n\n"
            "Antworte NUR im JSON Format: {\"allowed\": true/false, \"reason\": \"Begründung\"}"
        )
        
        result = agent_answer(prompt, role="OBSERVER")
        
        # Parsen der Antwort (orchestrator gibt dict zurück)
        # Falls orchestrator text zurückgibt, hier parsen
        res_text = result.get("text", "")
        try:
            res_json = json.loads(res_text)
            return res_json.get("allowed", False), res_json.get("reason", "Keine Begründung")
        except:
            # Fallback falls LLM kein valides JSON liefert
            if "true" in res_text.lower() and "allowed" in res_text.lower():
                return True, ""
            return False, "Observer konnte LLM-Antwort nicht validieren."

    def _log_veto(self, action_name: str, args: dict, reason: str):
        """Protokolliert das Veto über self_learning."""
        context = f"Aktion: {action_name}, Args: {json.dumps(args)}"
        log_correction(f"VETO durch Observer: {reason}", context)
        print(f"!!! OBSERVER VETO: {reason} !!!")
