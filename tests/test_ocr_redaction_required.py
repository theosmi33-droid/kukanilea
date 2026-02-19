from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.autonomy import ocr as ocr_mod
from app.autonomy.ocr import submit_ocr_for_source_file
from app.knowledge.core import knowledge_policy_update


def _mock_tesseract_binary(monkeypatch) -> None:
    def _resolve(requested_bin=None, env=None, *, platform_name=None):
        selected = str(requested_bin or "/usr/bin/tesseract")
        source = "explicit" if requested_bin else "path"
        return ocr_mod.ResolvedTesseractBin(
            requested=requested_bin,
            resolved_path=selected,
            exists=True,
            executable=True,
            allowlisted=True,
            allowlist_reason="matched_prefix",
            allowed_prefixes=("/usr/bin",),
            resolution_source=source,
        )

    monkeypatch.setattr(ocr_mod, "resolve_tesseract_binary", _resolve)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
                "redact.png",
                "hash-5",
                "fp-5",
                "new",
                _now_iso(),
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def test_ocr_persists_redacted_text_only(tmp_path: Path, monkeypatch) -> None:
    _init_core(tmp_path)
    knowledge_policy_update("TENANT_A", actor_user_id="dev", allow_ocr=True)
    source_file_id = "sf5"
    _insert_source_file("TENANT_A", source_file_id)
    image_path = tmp_path / "redact.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    class _Proc:
        returncode = 0
        stdout = "Mail me at private.person@example.com phone +49 170 1234567"
        stderr = ""

    _mock_tesseract_binary(monkeypatch)
    monkeypatch.setattr(ocr_mod.subprocess, "run", lambda *_a, **_k: _Proc())

    result = submit_ocr_for_source_file(
        tenant_id="TENANT_A",
        actor_user_id="dev",
        source_file_id=source_file_id,
        abs_path=image_path,
    )
    assert result["ok"] is True

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT body
            FROM knowledge_chunks
            WHERE tenant_id='TENANT_A' AND source_type='ocr'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
        job = con.execute(
            """
            SELECT redacted_text
            FROM autonomy_ocr_jobs
            WHERE tenant_id='TENANT_A'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    body = str(row["body"] or "").lower()
    assert "private.person@example.com" not in body
    assert "+49 170" not in body
    assert "[redacted-email]" in body
    assert job is not None
    redacted_text = str(job["redacted_text"] or "").lower()
    assert "private.person@example.com" not in redacted_text
    assert "+49 170" not in redacted_text
    assert "[redacted-email]" in redacted_text
