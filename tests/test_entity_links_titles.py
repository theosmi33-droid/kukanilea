from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.entity_links.display import entity_display_title, sanitize_title
from app.lead_intake.core import leads_create

_PHONE_LIKE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def test_sanitize_title_removes_controls_and_clamps() -> None:
    text = "\x00Alpha\nBeta\rGamma\t" + ("x" * 200)
    out = sanitize_title(text, max_len=80)
    assert "\x00" not in out
    assert "\n" not in out
    assert "\r" not in out
    assert len(out) <= 80
    assert out.startswith("Alpha Beta Gamma")


def test_entity_display_title_tenant_filter_and_unknown_fallback(
    tmp_path: Path,
) -> None:
    _init_core(tmp_path)
    lead_id = leads_create(
        tenant_id="TENANT_A",
        source="manual",
        contact_name="Kontakt",
        contact_email="person@example.com",
        contact_phone="+491701234567",
        subject="Anfrage von person@example.com",
        message="Ruf mich an: +491701234567",
    )

    con = sqlite3.connect(str(core.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        own = entity_display_title(con, "TENANT_A", "lead", lead_id)
        other = entity_display_title(con, "TENANT_B", "lead", lead_id)
        unknown = entity_display_title(con, "TENANT_A", "does_not_exist", "x")
    finally:
        con.close()

    assert own["type"] == "lead"
    assert own["href"] == f"/leads/{lead_id}"
    assert "@" not in own["title"]
    assert not _PHONE_LIKE.search(own["title"])
    assert own["title"] != "(unbekannt)"

    assert other["title"] == "(unbekannt)"
    assert other["href"] == ""

    assert unknown["title"] == "(unbekannt)"
    assert unknown["href"] == ""
