from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Config

PARSER_VERSION = "2026-03-05"


@dataclass(frozen=True)
class IngestionArtifact:
    artifact_hash: str
    artifact_path: str
    byte_size: int


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _normalize_source(source: str) -> str:
    normalized = str(source or "text").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "image": "photo",
        "jpg": "photo",
        "jpeg": "photo",
        "png": "photo",
        "voice": "voice_transcript",
        "transcript": "voice_transcript",
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in {"photo", "pdf", "text", "voice_transcript"} else "text"


def _extract_entities(raw_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = str(raw_text or "")
    entities: list[dict[str, Any]] = []
    suggested_tasks: list[dict[str, Any]] = []

    project_pattern = re.compile(r"(?:^|\n)\s*(?:project|projekt)\s*[:\-]\s*(.+)", re.IGNORECASE)
    task_pattern = re.compile(r"(?:^|\n)\s*(?:task|aufgabe|todo)\s*[:\-]\s*(.+)", re.IGNORECASE)
    date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")

    for match in project_pattern.finditer(text):
        name = match.group(1).strip()
        if not name:
            continue
        entities.append(
            {
                "entity_type": "project",
                "name": name,
                "confidence": 0.72,
                "source_span": [match.start(1), match.end(1)],
            }
        )

    for match in task_pattern.finditer(text):
        body = match.group(1).strip()
        if not body:
            continue
        due = None
        due_match = date_pattern.search(body)
        if due_match:
            due = due_match.group(1)
        task = {
            "title": body,
            "confidence": 0.78,
            "source_span": [match.start(1), match.end(1)],
        }
        if due:
            task["due_date"] = due
        suggested_tasks.append(task)
        entities.append(
            {
                "entity_type": "task",
                "title": body,
                "confidence": 0.78,
                "source_span": [match.start(1), match.end(1)],
            }
        )

    if not suggested_tasks:
        bullets = re.findall(r"(?:^|\n)\s*[-*]\s+(.+)", text)
        for line in bullets[:8]:
            suggested_tasks.append({"title": line.strip(), "confidence": 0.55})

    return entities, suggested_tasks


def store_artifact(*, tenant: str, source: str, payload_bytes: bytes, metadata: dict[str, Any] | None = None) -> IngestionArtifact:
    metadata = dict(metadata or {})
    artifact_hash = hashlib.sha256(payload_bytes).hexdigest()
    tenant_key = str(tenant or "default").strip() or "default"

    artifact_root = Path(Config.USER_DATA_ROOT) / "upload_artifacts" / tenant_key
    artifact_root.mkdir(parents=True, exist_ok=True)

    raw_path = artifact_root / f"{artifact_hash}.bin"
    if not raw_path.exists():
        raw_path.write_bytes(payload_bytes)

    sidecar = {
        "artifact_hash": artifact_hash,
        "source": _normalize_source(source),
        "tenant": tenant_key,
        "byte_size": len(payload_bytes),
        "metadata": metadata,
        "stored_at": _utc_now(),
    }
    (artifact_root / f"{artifact_hash}.json").write_text(_canonical_json(sidecar), encoding="utf-8")

    return IngestionArtifact(
        artifact_hash=artifact_hash,
        artifact_path=str(raw_path),
        byte_size=len(payload_bytes),
    )


def ingest_unstructured_input(
    *,
    source: str,
    tenant: str,
    text: str,
    metadata: dict[str, Any] | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    normalized_source = _normalize_source(source)
    normalized_ts = str(ts or _utc_now())
    normalized_tenant = str(tenant or "default").strip() or "default"
    metadata = dict(metadata or {})

    payload_bytes = text.encode("utf-8")
    artifact = store_artifact(
        tenant=normalized_tenant,
        source=normalized_source,
        payload_bytes=payload_bytes,
        metadata=metadata,
    )

    entities, suggested_tasks = _extract_entities(text)
    audit = {
        "artifact_hash": artifact.artifact_hash,
        "artifact_path": artifact.artifact_path,
        "parser_version": PARSER_VERSION,
        "ingested_at": normalized_ts,
        "byte_size": artifact.byte_size,
    }

    for item in entities:
        item["audit"] = {
            "artifact_hash": artifact.artifact_hash,
            "parser_version": PARSER_VERSION,
        }

    return {
        "source": normalized_source,
        "ts": normalized_ts,
        "tenant": normalized_tenant,
        "entities": entities,
        "suggested_tasks": suggested_tasks,
        "audit": audit,
    }
