from __future__ import annotations

from pathlib import Path

from app.omni.channels.email_sim import ingest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eml" / "sample_with_pii.eml"


def test_email_adapter_parses_fixture() -> None:
    rows = ingest("TENANT_A", FIXTURE)
    assert len(rows) == 1
    row = rows[0]
    assert row["channel"] == "email"
    assert row["direction"] == "inbound"
    assert row["channel_ref"] == "<sample-omni-001@example.test>"
    payload = row["raw_payload"]
    assert "qa-test-pii@example.com" in payload["from"]
    assert "qa-test-pii@example.com" in payload["body"]
    assert payload["subject"]


def test_email_adapter_html_fallback(tmp_path: Path) -> None:
    fixture = tmp_path / "html_only.eml"
    fixture.write_text(
        "\n".join(
            [
                "From: HTML Bot <html@example.test>",
                "To: Team <ops@example.test>",
                "Subject: HTML test",
                "Date: Mon, 15 Feb 2026 10:00:00 +0000",
                "Message-ID: <sample-omni-html@example.test>",
                "MIME-Version: 1.0",
                "Content-Type: text/html; charset=utf-8",
                "",
                "<html><body><h1>Hallo</h1><p>Nur <b>HTML</b></p></body></html>",
            ]
        ),
        encoding="utf-8",
    )
    rows = ingest("TENANT_A", fixture)
    assert len(rows) == 1
    payload = rows[0]["raw_payload"]
    assert payload["used_html_fallback"] is True
    assert "Hallo" in payload["body"]
