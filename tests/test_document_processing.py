from __future__ import annotations

import json
from pathlib import Path

from app.modules.upload.document_processing import (
    ensure_document_processing_tables,
    list_processing_queue,
    list_recent_uploads,
    register_document_upload,
    run_virus_scan_hook,
)


def test_register_document_upload_persists_metadata_queue_and_events(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "auth.sqlite3"
    file_path = tmp_path / "invoice.pdf"
    file_path.write_bytes(b"dummy")

    monkeypatch.chdir(tmp_path)

    ensure_document_processing_tables(db_path)
    payload = register_document_upload(
        file_path=file_path,
        tenant_id="tenant-a",
        file_hash="abc123",
        db_path=db_path,
    )

    uploads = list_recent_uploads("tenant-a", db_path=db_path)
    queue = list_processing_queue("tenant-a", db_path=db_path)

    assert payload["metadata"]["tenant"] == "tenant-a"
    assert uploads and uploads[0]["filename"] == "invoice.pdf"
    assert uploads[0]["hash"] == "abc123"
    assert uploads[0]["deadline_detection"]["status"] == "not_implemented"
    assert queue and queue[0]["status"] == "processed"
    assert queue[0]["payload"]["event_types"] == ["document.uploaded", "document.processed"]

    events_log = tmp_path / "instance" / "agent_events.jsonl"
    lines = [json.loads(line) for line in events_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    event_types = [item["type"] for item in lines]
    assert "document.uploaded" in event_types
    assert "document.processed" in event_types


def test_virus_scan_hook_defaults_to_pass_without_configuration(tmp_path) -> None:
    file_path = tmp_path / "f.txt"
    file_path.write_text("ok", encoding="utf-8")

    clean, reason = run_virus_scan_hook(file_path, "tenant-a")

    assert clean is True
    assert reason == "hook_not_configured"
