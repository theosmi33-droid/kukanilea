from __future__ import annotations

import os
import sys
from datetime import date

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.zugferd import ZugferdGenerator, InvoiceData, InvoiceParty

def test_zugferd_generation():
    print("Testing KUKANILEA ZUGFeRD Generation...")
    
    data = InvoiceData(
        invoice_id="RE-2026-001",
        invoice_date=date(2026, 2, 28),
        seller=InvoiceParty(
            name="Elektro Schmidt",
            street="Hauptstr. 10",
            zip_code="80331",
            city="München",
            vat_id="DE123456789"
        ),
        buyer=InvoiceParty(
            name="Max Mustermann",
            street="Nebenweg 5",
            zip_code="12345",
            city="Berlin"
        ),
        items=[],
        total_net=100.0,
        total_vat=19.0,
        total_gross=119.0
    )
    
    gen = ZugferdGenerator()
    xml = gen.generate_xml(data)
    
    print(f"Generated XML length: {len(xml)}")
    assert "CrossIndustryInvoice" in xml
    assert "RE-2026-001" in xml
    assert "Elektro Schmidt" in xml
    assert "119.00" in xml
    assert "urn:factur-x.eu:1p0:minimum" in xml

    print("ZUGFeRD Generation Test: PASS")

if __name__ == "__main__":
    test_zugferd_generation()
