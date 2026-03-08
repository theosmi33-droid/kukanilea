from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Config

PARSER_VERSION = "2026-03-05"
INGEST_ARTIFACT_QUOTA_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class IngestionArtifact:
    artifact_hash: str
    artifact_path: str
    byte_size: int


@dataclass(frozen=True)
class ExtractedText:
    text: str
    strategy: str
    warnings: tuple[str, ...] = ()


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


def _decode_with_fallbacks(payload_bytes: bytes) -> ExtractedText:
    warnings: list[str] = []
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return ExtractedText(text=payload_bytes.decode(encoding), strategy=f"decode:{encoding}", warnings=tuple(warnings))
        except UnicodeDecodeError:
            warnings.append(f"decode_failed:{encoding}")
    return ExtractedText(text=payload_bytes.decode("utf-8", errors="replace"), strategy="decode:utf-8-replace", warnings=tuple(warnings))


def extract_text_payload(
    *,
    payload_bytes: bytes,
    source: str,
    filename: str = "",
    content_type: str = "",
) -> ExtractedText:
    normalized_source = _normalize_source(source)
    lowered_filename = str(filename or "").lower()
    lowered_content_type = str(content_type or "").lower()

    if normalized_source == "voice_transcript":
        decoded = _decode_with_fallbacks(payload_bytes)
        return ExtractedText(text=decoded.text, strategy="voice_transcript", warnings=decoded.warnings)

    if normalized_source == "photo":
        decoded = _decode_with_fallbacks(payload_bytes)
        warning = "ocr_not_executed_payload_decode_only"
        if decoded.text.strip():
            return ExtractedText(text=decoded.text, strategy="photo:fallback-decode", warnings=decoded.warnings + (warning,))
        return ExtractedText(text="", strategy="photo:empty", warnings=decoded.warnings + (warning,))

    if normalized_source == "pdf" or lowered_filename.endswith(".pdf") or "pdf" in lowered_content_type:
        decoded = _decode_with_fallbacks(payload_bytes)
        warning = "pdf_ocr_not_available_payload_decode_only"
        return ExtractedText(text=decoded.text, strategy="pdf:fallback-decode", warnings=decoded.warnings + (warning,))

    decoded = _decode_with_fallbacks(payload_bytes)
    strategy = decoded.strategy

    if lowered_filename.endswith(".json") or "json" in lowered_content_type:
        try:
            obj = json.loads(decoded.text)
            flattened = json.dumps(obj, ensure_ascii=False, sort_keys=True)
            return ExtractedText(text=flattened, strategy="json:normalized", warnings=decoded.warnings)
        except json.JSONDecodeError:
            return ExtractedText(text=decoded.text, strategy=f"json:invalid:{strategy}", warnings=decoded.warnings + ("invalid_json",))

    if lowered_filename.endswith((".html", ".htm")) or "html" in lowered_content_type:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", decoded.text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return ExtractedText(text=text, strategy="html:stripped", warnings=decoded.warnings)

    return decoded


def _classify_document(*, text: str, source: str, metadata: dict[str, Any]) -> dict[str, Any]:
    lowered = str(text or "").lower()
    source_label = _normalize_source(source)
    scores = Counter()
    rationale: list[str] = []

    keyword_map = {
        "invoice": ["rechnung", "invoice", "betrag", "zahlbar"],
        "offer": ["angebot", "quotation", "offer"],
        "report": ["bericht", "protokoll", "report"],
        "task_list": ["aufgabe", "task", "todo", "to-do"],
        "email": ["subject:", "from:", "to:", "betreff:"],
    }
    for label, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in lowered:
                scores[label] += 1
                rationale.append(f"keyword:{label}:{keyword}")

    if source_label == "voice_transcript":
        scores["task_list"] += 1
        rationale.append("source:voice_transcript")
    if str(metadata.get("channel") or "").lower() == "mail":
        scores["email"] += 1
        rationale.append("metadata:channel=mail")

    best_label = "unknown"
    best_score = 0
    if scores:
        best_label, best_score = max(scores.items(), key=lambda item: (item[1], item[0]))

    confidence = round(min(0.95, 0.35 + (best_score * 0.15)), 2) if best_score else 0.2
    return {
        "label": best_label,
        "confidence": confidence,
        "scores": dict(sorted(scores.items())),
        "rationale": rationale[:12],
        "version": PARSER_VERSION,
    }


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
        current_usage = sum(path.stat().st_size for path in artifact_root.glob("*.bin") if path.is_file())
        if current_usage + len(payload_bytes) > INGEST_ARTIFACT_QUOTA_BYTES:
            raise ValueError("quota_exceeded")
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


def ingest_unstructured_bytes(
    *,
    source: str,
    tenant: str,
    payload_bytes: bytes,
    metadata: dict[str, Any] | None = None,
    filename: str = "",
    content_type: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    metadata = dict(metadata or {})
    extracted = extract_text_payload(
        payload_bytes=payload_bytes,
        source=source,
        filename=filename,
        content_type=content_type,
    )
    metadata.setdefault("extraction", {})
    metadata["extraction"] = {
        "strategy": extracted.strategy,
        "warnings": list(extracted.warnings),
        "filename": filename,
        "content_type": content_type,
    }

    payload = ingest_unstructured_input(
        source=source,
        tenant=tenant,
        text=extracted.text,
        metadata=metadata,
        ts=ts,
    )
    payload["classification"] = _classify_document(text=extracted.text, source=source, metadata=metadata)
    payload["extraction"] = {
        "strategy": extracted.strategy,
        "warnings": list(extracted.warnings),
        "text_length": len(extracted.text),
    }
    payload["proposed_actions"] = _build_proposed_actions(payload)
    return payload


def _build_proposed_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    projects = [entity for entity in payload.get("entities", []) if entity.get("entity_type") == "project"]
    tasks = payload.get("suggested_tasks", [])

    if projects:
        for project in projects[:3]:
            actions.append(
                {
                    "type": "create_project",
                    "title": str(project.get("name") or "Unbenanntes Projekt"),
                    "confidence": float(project.get("confidence") or 0.5),
                }
            )

    for task in tasks[:5]:
        actions.append(
            {
                "type": "create_task",
                "title": str(task.get("title") or "Neue Aufgabe"),
                "due_date": str(task.get("due_date") or ""),
                "confidence": float(task.get("confidence") or 0.5),
            }
        )
    return actions
