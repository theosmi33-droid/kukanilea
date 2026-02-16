from __future__ import annotations

import json
import re
import sqlite3
import zipfile
from pathlib import Path

import app.devtools.support_bundle as support_bundle

POSIX_ABS_RE = re.compile(r"(^|[^A-Za-z0-9])/(Users|home)/")
WIN_ABS_RE = re.compile(r"[A-Za-z]:\\")


def _init_core_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE knowledge_source_policies(tenant_id TEXT PRIMARY KEY, allow_ocr INTEGER)"
        )
        con.execute(
            "CREATE TABLE source_watch_config(tenant_id TEXT PRIMARY KEY, documents_inbox_dir TEXT)"
        )
        con.execute(
            "CREATE TABLE source_files(id TEXT PRIMARY KEY, tenant_id TEXT, basename TEXT)"
        )
        con.execute(
            "CREATE TABLE autonomy_ocr_jobs(id TEXT PRIMARY KEY, tenant_id TEXT, status TEXT)"
        )
        con.execute(
            "CREATE TABLE knowledge_chunks(id TEXT PRIMARY KEY, tenant_id TEXT, content TEXT)"
        )
        con.execute(
            "CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, payload_json TEXT)"
        )
        con.execute(
            "INSERT INTO knowledge_chunks(id, tenant_id, content) VALUES ('k1','dev','pilot+test@example.com')"
        )
        con.commit()
    finally:
        con.close()


def test_write_support_bundle_creates_expected_files_and_zip(
    tmp_path: Path, monkeypatch
) -> None:
    core_db = tmp_path / "core.sqlite3"
    _init_core_db(core_db)
    monkeypatch.setattr(support_bundle, "resolve_core_db_path", lambda: core_db)

    out_dir = tmp_path / "bundle"
    result = support_bundle.write_support_bundle(
        "dev",
        out_dir,
        doctor_result={
            "ok": False,
            "reason": "tesseract_missing",
            "stderr_tail": "Error opening data file /Users/test/tessdata/eng.traineddata",
            "note": "pilot+test@example.com",
        },
        sandbox_e2e_result={
            "ok": False,
            "reason": "job_not_found",
            "inbox_dir_used": "/Users/test/Documents OCR",
        },
        extra={"debug": "C:\\Users\\test\\foo"},
        zip_bundle=True,
    )

    assert result["ok"] is True
    assert (out_dir / "support_bundle_manifest.json").exists()
    assert (out_dir / "ocr_doctor.json").exists()
    assert (out_dir / "ocr_sandbox_e2e.json").exists()
    assert (out_dir / "env_summary.json").exists()
    assert (out_dir / "schema_snapshot.json").exists()
    zip_path = out_dir / "support_bundle.zip"
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(zf.namelist())
    assert names == sorted(result["files"])
    assert all(not name.endswith(".sqlite3") for name in names)

    schema_payload = json.loads((out_dir / "schema_snapshot.json").read_text())
    assert schema_payload["core_db_accessible"] is True
    assert "tables" in schema_payload
    assert "knowledge_source_policies" in schema_payload["tables"]
    assert "rows" not in json.dumps(schema_payload, sort_keys=True)

    manifest_payload = json.loads(
        (out_dir / "support_bundle_manifest.json").read_text()
    )
    assert manifest_payload["ok"] is True
    assert manifest_payload["zip_path"] is not None

    doctor_payload = json.loads((out_dir / "ocr_doctor.json").read_text())
    serialized = json.dumps(doctor_payload, sort_keys=True)
    assert "pilot+test@example.com" not in serialized
    assert POSIX_ABS_RE.search(serialized) is None
    assert WIN_ABS_RE.search(serialized) is None


def test_write_support_bundle_without_zip(tmp_path: Path, monkeypatch) -> None:
    core_db = tmp_path / "core.sqlite3"
    _init_core_db(core_db)
    monkeypatch.setattr(support_bundle, "resolve_core_db_path", lambda: core_db)

    out_dir = tmp_path / "bundle-nozip"
    result = support_bundle.write_support_bundle(
        "dev",
        out_dir,
        doctor_result={"ok": True, "reason": None},
        sandbox_e2e_result=None,
        zip_bundle=False,
    )
    assert result["ok"] is True
    assert result["zip_path"] is None
    assert not (out_dir / "support_bundle.zip").exists()
