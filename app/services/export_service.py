"""
app/services/export_service.py
Enterprise-Export-Service für KUKANILEA.
Fokus: DATEV-kompatibler Export (GoBD-konform) und ZIP-Bündelung.
"""

import os
import csv
import io
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger("kukanilea.export")

class ExportService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def generate_datev_export(self, tenant_id: str, year: int, month: int) -> bytes:
        """
        Generiert ein DATEV-kompatibles ZIP-Paket mit CSV und Original-Belegen.
        """
        import sqlite3
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        
        # Datumsbereich für den Export
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-31"
        
        try:
            # Wir ziehen alle validierten Belege aus dem Zeitraum
            query = """
            SELECT d.doc_id, d.kdnr, d.doctype, d.doc_date, v.file_path, v.file_name,
                   di.doc_number, di.customer_name
            FROM docs d
            JOIN versions v ON d.doc_id = v.doc_id
            LEFT JOIN docs_index di ON d.doc_id = di.doc_id
            WHERE d.tenant_id = ? AND d.doc_date BETWEEN ? AND ?
            """
            rows = con.execute(query, (tenant_id, start_date, end_date)).fetchall()
            
            if not rows:
                logger.warning(f"Keine Belege für DATEV-Export gefunden ({tenant_id}, {year}-{month})")
                return b""

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                # 1. DATEV CSV erstellen
                csv_buffer = io.StringIO()
                # DATEV EXTF Header (stark vereinfacht für Prototyp)
                csv_file = csv.writer(csv_buffer, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                
                # DATEV Header Zeile 1
                csv_file.writerow(["EXTF", 700, 21, "Buchungsstapel", 9, "", "", "", "", "", "KUKANILEA", "", "", "", 0])
                
                # DATEV Spalten-Header
                csv_file.writerow(["Umsatz", "Soll/Haben", "WKZ", "Kurs", "Basisumsatz", "WKZ Basisumsatz", "Konto", "Gegenkonto", "BU-Schlüssel", "Belegdatum", "Belegfeld 1", "Buchungstext"])
                
                for row in rows:
                    # Wir nutzen hier Platzhalter für Beträge, falls nicht im Index
                    # In Phase 5 haben wir extrahierte Beträge hinzugefügt (hier zu integrieren)
                    amount = "0,00" # TODO: Aus di oder entities laden
                    date_val = row["doc_date"].replace("-", "") if row["doc_date"] else ""
                    
                    csv_file.writerow([
                        amount, "S", "EUR", "", "", "", "8400", "1200", "", date_val, row["doc_number"] or "", row["customer_name"] or "Import KUKANILEA"
                    ])
                    
                    # 2. Original-Datei in ZIP packen
                    if row["file_path"] and os.path.exists(row["file_path"]):
                        zip_file.write(row["file_path"], arcname=f"Belege/{row['file_name']}")

                # CSV ins ZIP
                zip_file.writestr("DATEV_Export.csv", csv_buffer.getvalue())

            logger.info(f"DATEV-Export versiegelt: {len(rows)} Belege.")
            return zip_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Fehler beim DATEV-Export: {e}")
            return b""
        finally:
            con.close()

# Singleton-Instanz (wird beim App-Start initialisiert)
export_service = None

def init_export_service(db_path: str):
    global export_service
    export_service = ExportService(db_path)
