from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_email_import_valid_eml(tmp_path: Path) -> None:
    _init_core(tmp_path)
    eml = (
        b"From: sender@example.com\n"
        b"To: receiver@example.com\n"
        b"Subject: Hallo\n"
        b"Date: Tue, 04 Feb 2026 12:00:00 +0000\n"
        b"Message-ID: <abc@test>\n"
        b"Content-Type: text/plain; charset=utf-8\n\n"
        b"Dies ist ein Test."
    )

    email_id = core.emails_import_eml("TENANT_A", eml)

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM emails_cache WHERE id=?", (email_id,)
        ).fetchone()
        assert row is not None
        assert row["subject"] == "Hallo"
        assert "Test" in (row["body_text"] or "")
        assert row["raw_eml"] is not None
    finally:
        con.close()


def test_email_import_corrupt_eml_still_persists(tmp_path: Path) -> None:
    _init_core(tmp_path)
    broken = b"\xff\xfe\xfa\x00\x00\x01"

    email_id = core.emails_import_eml("TENANT_A", broken)

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM emails_cache WHERE id=?", (email_id,)
        ).fetchone()
        assert row is not None
        assert row["raw_eml"] is not None
        assert row["body_text"] in ("", None)
        assert row["notes"]
    finally:
        con.close()
