from __future__ import annotations

from app.mail import postfach_store
from unittest.mock import patch


def test_tenant_quota_guard_rejects_large_attachment(tmp_path, monkeypatch):
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(postfach_store.Config, "USER_DATA_ROOT", tmp_path)
    monkeypatch.setattr(postfach_store, "MAIL_ATTACHMENT_TENANT_QUOTA_BYTES", 4)

    refs: list[dict] = []

    def _capture_store(*_args, **kwargs):
        refs.append(kwargs["content_ref"])
        return "att-1"

    with patch("app.mail.postfach_store.store_message_attachment", side_effect=_capture_store):
        out = postfach_store.ingest_message_attachments(
            db_path,
            tenant_id="tenant-a",
            account_id="acc-1",
            message_id="msg-1",
            attachments=[
                {
                    "filename": "x.txt",
                    "mime_type": "text/plain",
                    "size_bytes": 5,
                    "content_bytes": b"12345",
                }
            ],
        )

    assert out["rejected"] == 1
    assert out["accepted"] == 0
    assert refs[0]["reason"] == "tenant_quota_exceeded"
