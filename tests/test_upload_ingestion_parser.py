from __future__ import annotations

import json
from pathlib import Path

from app.modules.upload.ingestion import ingest_unstructured_bytes, ingest_unstructured_input


def test_ingest_extracts_project_and_task_entities(tmp_path: Path, monkeypatch) -> None:
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)

    payload = ingest_unstructured_input(
        source="voice transcript",
        tenant="KUKANILEA",
        text="Projekt: Lighthouse Rollout\nAufgabe: Angebot prüfen bis 2026-04-01",
        metadata={"channel": "dictation"},
    )

    assert payload["source"] == "voice_transcript"
    assert payload["tenant"] == "KUKANILEA"
    assert payload["entities"]
    assert any(entity.get("entity_type") == "project" for entity in payload["entities"])
    assert payload["suggested_tasks"][0]["due_date"] == "2026-04-01"
    assert payload["audit"]["artifact_hash"]


def test_ingest_stores_artifact_and_sidecar_metadata(tmp_path: Path, monkeypatch) -> None:
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)

    payload = ingest_unstructured_input(
        source="text",
        tenant="tenant-a",
        text="- Erstes ToDo\n- Zweites ToDo",
        metadata={"source_file": "notes.txt"},
    )

    artifact_hash = payload["audit"]["artifact_hash"]
    artifact_bin = tmp_path / "upload_artifacts" / "tenant-a" / f"{artifact_hash}.bin"
    artifact_json = tmp_path / "upload_artifacts" / "tenant-a" / f"{artifact_hash}.json"

    assert artifact_bin.exists()
    assert artifact_json.exists()

    sidecar = json.loads(artifact_json.read_text(encoding="utf-8"))
    assert sidecar["artifact_hash"] == artifact_hash
    assert sidecar["metadata"]["source_file"] == "notes.txt"


def test_ingest_bytes_classification_and_action_suggestions_are_reproducible(tmp_path: Path, monkeypatch) -> None:
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)

    payload_a = ingest_unstructured_bytes(
        source="text",
        tenant="tenant-a",
        payload_bytes=b"Project: Solar Roof\nTask: Create offer draft by 2026-05-11",
        metadata={"channel": "mail"},
        filename="input.txt",
        content_type="text/plain",
    )
    payload_b = ingest_unstructured_bytes(
        source="text",
        tenant="tenant-a",
        payload_bytes=b"Project: Solar Roof\nTask: Create offer draft by 2026-05-11",
        metadata={"channel": "mail"},
        filename="input.txt",
        content_type="text/plain",
    )

    assert payload_a["classification"] == payload_b["classification"]
    assert payload_a["classification"]["label"] in {"offer", "task_list", "email"}
    assert payload_a["proposed_actions"]
    assert any(item["type"] == "create_project" for item in payload_a["proposed_actions"])
    assert any(item["type"] == "create_task" for item in payload_a["proposed_actions"])


def test_ingest_bytes_pdf_fallback_reports_extraction_warning(tmp_path: Path, monkeypatch) -> None:
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)

    payload = ingest_unstructured_bytes(
        source="pdf",
        tenant="tenant-a",
        payload_bytes=b"%PDF-1.4\nProject: Renovation\nTask: Follow up",
        metadata={},
        filename="scan.pdf",
        content_type="application/pdf",
    )

    warnings = payload["extraction"]["warnings"]
    assert "pdf_ocr_not_available_payload_decode_only" in warnings
    assert payload["classification"]["version"]


def test_ingest_bytes_handles_invalid_json_with_fallback_warning(tmp_path: Path, monkeypatch) -> None:
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)

    payload = ingest_unstructured_bytes(
        source="text",
        tenant="tenant-a",
        payload_bytes=b'{"broken":',
        metadata={},
        filename="broken.json",
        content_type="application/json",
    )

    assert payload["extraction"]["strategy"].startswith("json:invalid")
    assert "invalid_json" in payload["extraction"]["warnings"]


def test_ingest_enforces_per_tenant_artifact_quota(tmp_path: Path, monkeypatch) -> None:
    from app.config import Config

    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)

    quota = 32
    monkeypatch.setattr("app.modules.upload.ingestion.INGEST_ARTIFACT_QUOTA_BYTES", quota)

    ingest_unstructured_bytes(
        source="text",
        tenant="tenant-a",
        payload_bytes=b"a" * 24,
        metadata={},
    )

    try:
        ingest_unstructured_bytes(
            source="text",
            tenant="tenant-a",
            payload_bytes=b"b" * 16,
            metadata={},
        )
    except ValueError as exc:
        assert str(exc) == "quota_exceeded"
    else:
        raise AssertionError("Expected quota_exceeded when tenant artifact quota is exceeded")
