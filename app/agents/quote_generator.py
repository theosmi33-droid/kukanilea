"""
app/agents/quote_generator.py
Autonome Angebotsmaschine für KUKANILEA.
Generiert PDF-Angebote lokal mit reportlab.
"""

import os
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm

class QuoteGenerator:
    def __init__(self, output_dir: str = "instance/quotes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_pdf_quote(self, quote_data: dict) -> str:
        """
        Erstellt ein PDF-Angebot aus strukturierten Daten.
        quote_data Format: {
            "customer_name": str,
            "customer_address": str,
            "quote_number": str,
            "items": [{"name": str, "quantity": int, "price_per_unit": float, "total": float}],
            "total_net": float,
            "tax_rate": float,
            "total_gross": float
        }
        """
        filename = f"Angebot_{quote_data.get('quote_number', 'ENTWURF')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = self.output_dir / filename
        
        doc = SimpleDocTemplate(str(filepath), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # Header
        story.append(Paragraph("KUKANILEA HANDWERKSSERVICE", styles['Title']))
        story.append(Spacer(1, 1*cm))

        # Kundendaten
        story.append(Paragraph(f"An:<br/>{quote_data.get('customer_name', 'Unbekannt')}<br/>{quote_data.get('customer_address', '')}", styles['Normal']))
        story.append(Spacer(1, 1*cm))

        # Angebotsinfo
        story.append(Paragraph(f"<b>Angebot Nr: {quote_data.get('quote_number', 'ENTWURF')}</b>", styles['Heading2']))
        story.append(Paragraph(f"Datum: {datetime.now().strftime('%d.%m.%Y')}", styles['Normal']))
        story.append(Spacer(1, 0.5*cm))

        # Artikeltabelle
        data = [["Pos", "Bezeichnung", "Menge", "Einzelpreis", "Gesamt"]]
        for i, item in enumerate(quote_data.get("items", []), 1):
            data.append([
                str(i),
                item.get("name", ""),
                str(item.get("quantity", 0)),
                f"{item.get('price_per_unit', 0):.2f} €",
                f"{item.get('total', 0):.2f} €"
            ])

        data.append(["", "", "", "Gesamt Netto:", f"{quote_data.get('total_net', 0):.2f} €"])
        data.append(["", "", "", f"USt ({int(quote_data.get('tax_rate', 0.19)*100)}%):", f"{(quote_data.get('total_gross', 0) - quote_data.get('total_net', 0)):.2f} €"])
        data.append(["", "", "", "<b>Gesamt Brutto:</b>", f"<b>{quote_data.get('total_gross', 0):.2f} €</b>"])

        t = Table(data, colWidths=[1*cm, 8*cm, 2*cm, 3*cm, 3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -4), 1, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ]))
        story.append(t)
        
        story.append(Spacer(1, 2*cm))
        story.append(Paragraph("Vielen Dank für Ihre Anfrage. Wir freuen uns auf eine Zusammenarbeit.", styles['Italic']))

        doc.build(story)
        
        # GoBD Immutability Hashing
        import hashlib
        from app.models.rule import get_sa_session
        from app.models.price import DocumentHash
        
        with open(filepath, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        session = get_sa_session()
        try:
            hash_entry = DocumentHash(filepath=str(filepath), sha256_hash=file_hash)
            session.add(hash_entry)
            session.commit()
        except Exception as e:
            print(f"Fehler beim Speichern des GoBD Hashs: {e}")
        finally:
            session.close()

        return str(filepath)
