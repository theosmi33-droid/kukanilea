from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, Optional

from app.tools.base_tool import BaseTool
from app.tools.registry import registry
from app.core.zugferd import ZugferdGenerator, InvoiceData, InvoiceParty

class ZugferdTool(BaseTool):
    """
    Generates ZUGFeRD-compatible XML for machine-readable invoices.
    """

    name = "generate_zugferd_xml"
    description = "Erstellt eine ZUGFeRD-kompatible XML-Datei basierend auf Rechnungsdaten."
    input_schema = {
        "type": "object",
        "properties": {
            "invoice_id": {"type": "string"},
            "amount_net": {"type": "number"},
            "amount_vat": {"type": "number"},
            "seller_name": {"type": "string"},
            "buyer_name": {"type": "string"}
        },
        "required": ["invoice_id", "amount_net", "amount_vat", "seller_name", "buyer_name"]
    }

    def run(self, **kwargs) -> Any:
        try:
            # Map simple flat inputs to complex structure
            # In a real app, these would come from the database/OCR
            data = InvoiceData(
                invoice_id=kwargs["invoice_id"],
                invoice_date=date.today(),
                seller=InvoiceParty(
                    name=kwargs["seller_name"],
                    street="Musterstraße 1",
                    zip_code="12345",
                    city="Musterstadt"
                ),
                buyer=InvoiceParty(
                    name=kwargs["buyer_name"],
                    street="Kundenweg 2",
                    zip_code="54321",
                    city="Kundenstadt"
                ),
                items=[],
                total_net=kwargs["amount_net"],
                total_vat=kwargs["amount_vat"],
                total_gross=kwargs["amount_net"] + kwargs["amount_vat"]
            )
            
            generator = ZugferdGenerator()
            xml_content = generator.generate_xml(data)
            
            return {
                "status": "success",
                "xml": xml_content,
                "format": "ZUGFeRD 2.1.1 (Factur-X) Minimum"
            }
        except Exception as e:
            return {"error": str(e)}

# Register tool
registry.register(ZugferdTool())
