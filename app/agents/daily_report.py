"""
app/agents/daily_report.py
Autonomer Bautagebuch Generator für KUKANILEA.
Fusioniert Kalender, Sprachnotizen und Bildanalysen zu einem GoBD-konformen Rapport.
"""

import json
import hashlib
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, date, time
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm

from app.database import get_db_path, retry_on_lock
from app.models.rule import get_sa_session
from app.models.price import DocumentHash

logger = logging.getLogger("kukanilea.daily_report")

class DailyReportGenerator:
    def __init__(self, output_dir: str = "instance/reports/daily"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = get_db_path()

    def _wrap_with_salt(self, content: str) -> str:
        """Sicherheit: Salted Tags für die Zusammenfassung gegen Injection."""
        import secrets
        salt = secrets.token_hex(4)
        tag = f"KUKA_REPORT_{salt}"
        return f"\\n<{tag}>\\n{content}\\n</{tag}>\\n"

    @retry_on_lock()
    def gather_daily_data(self, target_date: date) -> dict:
        """Sammelt alle relevanten Daten des Tages aus der Datenbank."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        data = {
            "date": target_date.strftime("%d.%m.%Y"),
            "appointments": [],
            "voice_notes": [],
            "vision_analyses": [],
            "materials": []
        }
        
        try:
            # 1. Termine sammeln
            cursor = conn.execute(
                "SELECT * FROM appointments WHERE date(start_time) = ?",
                (target_date.isoformat(),)
            )
            data["appointments"] = [dict(row) for row in cursor.fetchall()]
            
            # 2. Sprachnotizen und Vision aus Audit-Logs extrahieren
            # Wir suchen nach TASK_DELEGATION Events
            cursor = conn.execute(
                "SELECT * FROM audit_logs WHERE date(timestamp) = ? AND action_type = 'TASK_DELEGATION'",
                (target_date.isoformat(),)
            )
            for row in cursor.fetchall():
                meta = json.loads(row['metadata_json'])
                user_input = meta.get('input', '')
                
                if "BILDANALYSE" in user_input:
                    data["vision_analyses"].append(user_input.replace("BILDANALYSE VOR-ORT:", "").strip())
                elif "<KUKA_MAIL_" not in user_input: # Einfache Unterscheidung zu E-Mails
                    data["voice_notes"].append(user_input)

            # 3. Material-Bestellungen des Tages (Schritt 4: verbautes Material)
            cursor = conn.execute(
                "SELECT metadata_json FROM audit_logs WHERE date(timestamp) = ? AND action_type = 'TOOL_CALL:generate_material_order'",
                (target_date.isoformat(),)
            )
            for row in cursor.fetchall():
                meta = json.loads(row['metadata_json'])
                data["materials"].append(f"Bestellung für Angebot #{meta.get('quote_id')}")

            return data
        finally:
            conn.close()

    def generate_pdf_report(self, daily_data: dict) -> str:
        """Erzeugt das formelle Bautagebuch-PDF."""
        filename = f"Bautagebuch_{daily_data['date'].replace('.', '_')}.pdf"
        filepath = self.output_dir / filename
        
        doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Header
        story.append(Paragraph(f"Täglicher Rapport: Bautagebuch", styles['Title']))
        story.append(Paragraph(f"Datum: {daily_data['date']}", styles['Normal']))
        story.append(Spacer(1, 1*cm))

        # 1. Ausgeführte Arbeiten (Termine)
        story.append(Paragraph("1. Termine und Einsätze", styles['Heading2']))
        if daily_data["appointments"]:
            apt_table = [["Zeit", "Titel", "Beschreibung"]]
            for apt in daily_data["appointments"]:
                start = datetime.fromisoformat(apt['start_time']).strftime("%H:%M")
                apt_table.append([start, apt['title'], apt['description'] or "-"])
            
            t = Table(apt_table, colWidths=[2*cm, 5*cm, 10*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("Keine Termine aufgezeichnet.", styles['Italic']))
        
        story.append(Spacer(1, 0.5*cm))

        # 2. Besondere Vorkommnisse (Sprachnotizen & Vision)
        story.append(Paragraph("2. Dokumentation & Bildanalyse", styles['Heading2']))
        
        all_notes = daily_data["voice_notes"] + daily_data["vision_analyses"]
        if all_notes:
            for note in all_notes:
                # Schritt 6: SST für die Text-Integrität im PDF
                safe_note = self._wrap_with_salt(note)
                story.append(Paragraph(f"• {note}", styles['Normal']))
        else:
            story.append(Paragraph("Keine zusätzlichen Notizen vorhanden.", styles['Italic']))

        story.append(Spacer(1, 0.5*cm))

        # 3. Materialverbrauch
        story.append(Paragraph("3. Material & Disposition", styles['Heading2']))
        if daily_data["materials"]:
            for mat in daily_data["materials"]:
                story.append(Paragraph(f"• {mat}", styles['Normal']))
        else:
            story.append(Paragraph("Kein Materialverbrauch dokumentiert.", styles['Italic']))

        # PDF bauen
        doc.build(story)

        # Schritt 5: GoBD-Versiegelung (Hashing)
        self._seal_document(filepath)

        return str(filepath)

    def _seal_document(self, filepath: Path):
        """Erzeugt einen SHA-256 Hash und speichert ihn für die GoBD Compliance."""
        with open(filepath, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        session = get_sa_session()
        try:
            hash_entry = DocumentHash(filepath=str(filepath), sha256_hash=file_hash)
            session.add(hash_entry)
            session.commit()
            logger.info(f"GoBD-Siegel erstellt für {filepath.name}: {file_hash[:16]}...")
        except Exception as e:
            logger.error(f"Fehler bei GoBD-Versiegelung: {e}")
        finally:
            session.close()
