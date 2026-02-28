from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional
from xml.etree import ElementTree as ET
from pydantic import BaseModel, Field

logger = logging.getLogger("kukanilea.zugferd")

class InvoiceParty(BaseModel):
    name: str
    street: str
    city: str
    zip_code: str
    country_code: str = "DE"
    vat_id: Optional[str] = None

class InvoiceItem(BaseModel):
    name: str
    quantity: float
    unit_code: str = "HUR"  # Hours, use 'C62' for pieces
    price: float
    tax_rate: float = 19.0

class InvoiceData(BaseModel):
    invoice_id: str
    invoice_date: date
    currency: str = "EUR"
    seller: InvoiceParty
    buyer: InvoiceParty
    items: List[InvoiceItem]
    total_net: float
    total_vat: float
    total_gross: float

class ZugferdGenerator:
    """
    Generates ZUGFeRD 2.1.1 (Factur-X) compatible XML (MINIMUM/BASIC profile).
    """

    def generate_xml(self, data: InvoiceData) -> str:
        """
        Creates the CrossIndustryInvoice XML.
        """
        # Namespaces
        rsm = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
        ram = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
        qdt = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
        udt = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

        ET.register_namespace('rsm', rsm)
        ET.register_namespace('ram', ram)
        ET.register_namespace('qdt', qdt)
        ET.register_namespace('udt', udt)

        root = ET.Element(f"{{{rsm}}}CrossIndustryInvoice")

        # ExchangedDocumentContext
        ctx = ET.SubElement(root, f"{{{ram}}}ExchangedDocumentContext")
        guideline = ET.SubElement(ctx, f"{{{ram}}}GuidelineSpecifiedDocumentContextParameter")
        ET.SubElement(guideline, f"{{{ram}}}ID").text = "urn:factur-x.eu:1p0:minimum"

        # ExchangedDocument
        doc = ET.SubElement(root, f"{{{rsm}}}ExchangedDocument")
        ET.SubElement(doc, f"{{{ram}}}ID").text = data.invoice_id
        ET.SubElement(doc, f"{{{ram}}}TypeCode").text = "380" # Commercial Invoice
        issue_date = ET.SubElement(doc, f"{{{ram}}}IssueDateTime")
        ET.SubElement(issue_date, f"{{{udt}}}DateTimeString", format="102").text = data.invoice_date.strftime("%Y%m%d")

        # SupplyChainTradeTransaction
        transaction = ET.SubElement(root, f"{{{rsm}}}SupplyChainTradeTransaction")
        
        # We'll skip individual LineItems for MINIMUM profile to keep it lightweight
        # and GoBD compliant for basic archiving.
        
        # Agreement
        agreement = ET.SubElement(transaction, f"{{{ram}}}ApplicableHeaderTradeAgreement")
        
        # Seller
        seller = ET.SubElement(agreement, f"{{{ram}}}SellerTradeParty")
        ET.SubElement(seller, f"{{{ram}}}Name").text = data.seller.name
        seller_addr = ET.SubElement(seller, f"{{{ram}}}PostalTradeAddress")
        ET.SubElement(seller_addr, f"{{{ram}}}PostcodeCode").text = data.seller.zip_code
        ET.SubElement(seller_addr, f"{{{ram}}}LineOne").text = data.seller.street
        ET.SubElement(seller_addr, f"{{{ram}}}CityName").text = data.seller.city
        ET.SubElement(seller_addr, f"{{{ram}}}CountryID").text = data.seller.country_code
        
        if data.seller.vat_id:
            tax_reg = ET.SubElement(seller, f"{{{ram}}}SpecifiedTaxRegistration")
            ET.SubElement(tax_reg, f"{{{ram}}}ID", schemeID="VA").text = data.seller.vat_id

        # Buyer
        buyer = ET.SubElement(agreement, f"{{{ram}}}BuyerTradeParty")
        ET.SubElement(buyer, f"{{{ram}}}Name").text = data.buyer.name
        buyer_addr = ET.SubElement(buyer, f"{{{ram}}}PostalTradeAddress")
        ET.SubElement(buyer_addr, f"{{{ram}}}PostcodeCode").text = data.buyer.zip_code
        ET.SubElement(buyer_addr, f"{{{ram}}}LineOne").text = data.buyer.street
        ET.SubElement(buyer_addr, f"{{{ram}}}CityName").text = data.buyer.city
        ET.SubElement(buyer_addr, f"{{{ram}}}CountryID").text = data.buyer.country_code

        # Delivery
        delivery = ET.SubElement(transaction, f"{{{ram}}}ApplicableHeaderTradeDelivery")
        # Event date could be added here

        # Settlement
        settlement = ET.SubElement(transaction, f"{{{ram}}}ApplicableHeaderTradeSettlement")
        ET.SubElement(settlement, f"{{{ram}}}InvoiceCurrencyCode").text = data.currency
        
        # Summary
        monetary_sum = ET.SubElement(settlement, f"{{{ram}}}SpecifiedTradeSettlementHeaderMonetarySummation")
        ET.SubElement(monetary_sum, f"{{{ram}}}LineTotalAmount").text = f"{data.total_net:.2f}"
        ET.SubElement(monetary_sum, f"{{{ram}}}TaxBasisTotalAmount").text = f"{data.total_net:.2f}"
        ET.SubElement(monetary_sum, f"{{{ram}}}TaxTotalAmount", currencyID=data.currency).text = f"{data.total_vat:.2f}"
        ET.SubElement(monetary_sum, f"{{{ram}}}GrandTotalAmount").text = f"{data.total_gross:.2f}"
        ET.SubElement(monetary_sum, f"{{{ram}}}DuePayableAmount").text = f"{data.total_gross:.2f}"

        return ET.tostring(root, encoding="unicode", xml_declaration=True)
