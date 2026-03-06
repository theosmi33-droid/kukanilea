from __future__ import annotations

import json
from pathlib import Path

from app.modules.upload.ingestion import ingest_unstructured_input


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
