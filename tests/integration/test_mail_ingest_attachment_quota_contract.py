from __future__ import annotations

from app.mail import postfach_store
from unittest.mock import patch


def test_mail_ingest_attachment_contract_reports_rejected_reason(tmp_path, monkeypatch):
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(postfach_store.Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(postfach_store, "MAIL_ATTACHMENT_TENANT_QUOTA_BYTES", 3)

    refs: list[dict] = []

    def _capture_store(*_args, **kwargs):
        refs.append(kwargs["content_ref"])
        return "att-2"

    with patch("app.mail.postfach_store.store_message_attachment", side_effect=_capture_store):
        out = postfach_store.ingest_message_attachments(
            db_path,
            tenant_id="tenant-b",
            account_id="acc-2",
            message_id="msg-2",
            attachments=[
                {
                    "filename": "invoice.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 4,
                    "content_bytes": b"1234",
                }
            ],
        )

    assert out["processed"] == 1
    assert out["rejected"] == 1
    assert out["accepted"] == 0
    assert refs[0]["reason"] == "tenant_quota_exceeded"
