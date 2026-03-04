from __future__ import annotations

from pathlib import Path

from app.core import rag_sync


class _AlwaysFailMemoryManager:
    def __init__(self, *_args, **_kwargs):
        pass

    def store_memory(self, **_kwargs):
        return False


def test_sync_document_to_memory_writes_dlq_on_embedding_fail(monkeypatch, tmp_path: Path) -> None:
    captured = []

    def _capture(file_path: Path, tenant_id: str, reason: str, context=None) -> None:
        captured.append({
            "file": file_path.name,
            "tenant": tenant_id,
            "reason": reason,
            "context": context or {},
        })

    monkeypatch.setattr(rag_sync, "MemoryManager", _AlwaysFailMemoryManager)
    monkeypatch.setattr(rag_sync, "write_dead_letter_marker", _capture)

    stored = rag_sync.sync_document_to_memory(
        tenant_id="tenant-a",
        doc_id="doc-1",
        file_name="invoice.pdf",
        text="X" * 3000,
        metadata={"kind": "invoice"},
    )

    assert stored == 0
    assert captured, "DLQ marker should be written when all embedding writes fail"
    assert all(item["reason"] == "RAG_SYNC_EMBEDDING_FAILED" for item in captured)
