from __future__ import annotations

import json

from app.omni.hub import redact_payload


def test_redaction_replaces_pii_and_tokenizes_headers() -> None:
    redacted, findings = redact_payload(
        {
            "from": "QA Bot <qa-test-pii@example.com>",
            "to": "Ops <ops@example.test>, Alice <alice@example.net>",
            "subject": "Bitte Rueckruf +49 151 12345678",
            "body": "Mail qa-test-pii@example.com und Telefon +49 151 12345678",
        }
    )
    payload_text = json.dumps(redacted, sort_keys=True)
    assert "qa-test-pii@example.com" not in payload_text
    assert "+49 151 12345678" not in payload_text
    assert redacted["from_domain"] == "example.com"
    assert redacted["to_domains"] == ["example.net", "example.test"]
    assert redacted["from_token"]
    assert len(redacted["to_tokens"]) == 2
    assert "[redacted-phone]" in str(redacted["subject_redacted"])
    assert "[redacted-phone]" in str(redacted["body_redacted"])
    assert findings["from_tokenized"] is True
    assert findings["to_token_count"] == 2
