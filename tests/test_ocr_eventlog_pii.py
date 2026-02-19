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
                "private.png",
                "hash-6",
                "fp-6",
                "new",
                _now_iso(),
                _now_iso(),
            ),
        )
        con.commit()
    finally:
        con.close()


def test_ocr_events_do_not_contain_paths_filenames_or_text(
    tmp_path: Path, monkeypatch
) -> None:
    _init_core(tmp_path)
    knowledge_policy_update("TENANT_A", actor_user_id="dev", allow_ocr=True)
    source_file_id = "sf6"
    _insert_source_file("TENANT_A", source_file_id)
    image_path = tmp_path / "private.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\npayload")

    class _Proc:
        returncode = 0
        stdout = "subject confidential and mail me at x@example.com"
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
        rows = con.execute(
            """
            SELECT event_type, payload_json
            FROM events
            WHERE event_type LIKE 'autonomy_ocr_%'
               OR event_type='knowledge_ocr_ingested'
            ORDER BY id ASC
            """
        ).fetchall()
    finally:
        con.close()

    assert rows
    payloads = "\n".join(str(r["payload_json"] or "") for r in rows).lower()
    assert str(image_path).lower() not in payloads
    assert "private.png" not in payloads
    assert "x@example.com" not in payloads
    assert "confidential" not in payloads
