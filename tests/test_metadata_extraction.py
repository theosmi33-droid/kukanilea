from __future__ import annotations

from app.autonomy.source_scan import extract_filename_metadata


def test_metadata_extracts_date_doctype_and_customer_token() -> None:
    data = extract_filename_metadata("kunden/Rechnung_2026-02-15_KD-1234.pdf")
    assert data["doctype"] == "invoice"
    assert data["date_iso"] == "2026-02-15"
    assert data["customer_token"] == "KD-1234"


def test_metadata_supports_multiple_date_formats() -> None:
    a = extract_filename_metadata("offer_20260215.txt")
    b = extract_filename_metadata("bericht_15-02-2026.txt")
    c = extract_filename_metadata("contract_15.02.2026.txt")
    assert a.get("date_iso") == "2026-02-15"
    assert b.get("date_iso") == "2026-02-15"
    assert c.get("date_iso") == "2026-02-15"


def test_metadata_ambiguous_or_invalid_date_is_not_set() -> None:
    data = extract_filename_metadata("invoice_2026-02-15_2026-02-16.txt")
    assert "date_iso" not in data

    invalid = extract_filename_metadata("invoice_2026-02-30.txt")
    assert "date_iso" not in invalid


def test_metadata_doctype_mapping_and_customer_token_strictness() -> None:
    offer = extract_filename_metadata("Angebot_final_CUST0012.pdf")
    other = extract_filename_metadata("misc_document.txt")
    assert offer["doctype"] == "offer"
    assert offer.get("customer_token") == "CUST-0012"
    assert other["doctype"] == "other"
    assert "customer_token" not in other
