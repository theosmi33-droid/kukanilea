from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy.ocr import submit_ocr_for_source_file
from app.knowledge.core import knowledge_policy_update


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _insert_source_file(tenant_id: str, source_file_id: str) -> None:
    con = sqlite3.connect(str(core.DB_PATH))
    try:
        con.execute(
            """
            INSERT INTO source_files(
              id, tenant_id, source_kind, basename, path_hash, fingerprint, status,
              last_seen_at, first_seen_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                source_file_id,
                tenant_id,
                "document",
                "doc.pdf",
                "hash-4",
                "fp-4",
                "new",
                _now_iso(),
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def test_ocr_pdf_is_now_supported(tmp_path: Path) -> None:
    _init_core(tmp_path)
    knowledge_policy_update("TENANT_A", actor_user_id="dev", allow_ocr=True)
    source_file_id = "sf4"
    _insert_source_file("TENANT_A", source_file_id)
    pdf_path = tmp_path / "doc.pdf"
    # Create a minimal valid PDF or just enough to not crash fitz if mocked
    pdf_path.write_bytes(b"%PDF-1.7\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Count 1/Kids[3 0 R]>>\nendobj\n3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF")

    # We might need to mock fitz or the OCR process if we don't have tesseract
    result = submit_ocr_for_source_file(
        tenant_id="TENANT_A",
        actor_user_id="dev",
        source_file_id=source_file_id,
        abs_path=pdf_path,
    )
    # The result will depend on if tesseract is installed, but it should NOT be 'pdf_not_supported'
    assert result["error_code"] != "pdf_not_supported"
