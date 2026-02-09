from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class JobState(str, Enum):
    RECEIVED = "RECEIVED"
    STORED = "STORED"
    EXTRACTED = "EXTRACTED"
    ENRICHED = "ENRICHED"
    INDEXED = "INDEXED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class Document:
    doc_id: str
    tenant_id: str
    kdnr: str
    file_name: str
    file_path: str
    created_at: datetime


@dataclass(frozen=True)
class IngestJob:
    job_id: str
    tenant_id: str
    source_path: str
    state: JobState
    created_at: datetime


@dataclass(frozen=True)
class ExtractResult:
    job_id: str
    text: str
    used_ocr: bool


@dataclass(frozen=True)
class ArchiveDecision:
    job_id: str
    destination_path: str
    reason: str
    approved_by: Optional[str] = None
