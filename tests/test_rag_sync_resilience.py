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


def test_sync_tenant_intelligence_uses_tenant_scoped_memory_files(tmp_path: Path) -> None:
    db_path = tmp_path / "core.db"
    memory_file = tmp_path / "MEMORY.md"

    rag = rag_sync.RAGSync(db_path=db_path, memory_file=memory_file)
    rag.sync_tenant_intelligence("tenant-a")
    rag.sync_tenant_intelligence("tenant-b")

    tenant_a_file = tmp_path / "MEMORY__tenant-a.md"
    tenant_b_file = tmp_path / "MEMORY__tenant-b.md"

    assert tenant_a_file.exists()
    assert tenant_b_file.exists()
    assert "Tenant: tenant-a" in tenant_a_file.read_text(encoding="utf-8")
    assert "Tenant: tenant-b" in tenant_b_file.read_text(encoding="utf-8")


def test_truncate_memory_text_enforces_byte_limit() -> None:
    oversized = "x" * (rag_sync._MAX_MEMORY_BYTES + 1000)
    truncated = rag_sync._truncate_memory_text(oversized)

    assert truncated.startswith("... (older entries truncated)\n")
    assert len(truncated.encode("utf-8")) <= (rag_sync._KEEP_MEMORY_BYTES + 128)
