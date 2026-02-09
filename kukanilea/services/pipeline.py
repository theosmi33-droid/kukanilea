from __future__ import annotations

from dataclasses import dataclass

from kukanilea.domain.models import JobState


@dataclass(frozen=True)
class PipelineStep:
    name: str
    state: JobState


PIPELINE = [
    PipelineStep("receive", JobState.RECEIVED),
    PipelineStep("store", JobState.STORED),
    PipelineStep("extract", JobState.EXTRACTED),
    PipelineStep("enrich", JobState.ENRICHED),
    PipelineStep("index", JobState.INDEXED),
    PipelineStep("archive", JobState.ARCHIVED),
]
