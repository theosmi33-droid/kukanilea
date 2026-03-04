from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app.core.upload_pipeline import (
    _clamav_optional_enabled,
    apply_layout_corrections,
    collect_manual_corrections,
    compute_layout_hash,
)


def test_compute_layout_hash_is_stable_for_normalized_text() -> None:
    text_a = "  Rechnung   2026 \n\n Kunde  1001  \n"
    text_b = "Rechnung 2026\nKunde 1001"

    assert compute_layout_hash(text_a) == compute_layout_hash(text_b)


def test_collect_manual_corrections_returns_only_changed_fields() -> None:
    original = {
        "doctype_suggested": "RECHNUNG",
        "kdnr_suggested": "1001",
        "name_suggestions": ["Muster GmbH"],
    }
    final = {
        "doctype": "RECHNUNG",
        "kdnr": "2002",
        "name": "Muster GmbH",
    }

    assert collect_manual_corrections(original, final) == [("kdnr", "2002")]


def test_apply_layout_corrections_updates_supported_suggestion_keys() -> None:
    suggestions = {"doctype_suggested": "SONSTIGES", "name_suggested": "Alt"}
    corrections = {"doctype": "RECHNUNG", "name": "Neu Name", "ignored": "x"}

    updated, provenance = apply_layout_corrections(suggestions, corrections)

    assert updated["doctype_suggested"] == "RECHNUNG"
    assert updated["name_suggested"] == "Neu Name"
    assert "ignored" not in updated
    assert provenance == {
        "doctype_suggested": "aus frueherer Korrektur",
        "name_suggested": "aus frueherer Korrektur",
    }


def test_clamav_optional_enabled_only_for_test_like_runtime(monkeypatch) -> None:
    monkeypatch.setenv("CLAMAV_OPTIONAL", "1")
    monkeypatch.setenv("KUKANILEA_ENV", "prod")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert _clamav_optional_enabled() is False

    monkeypatch.setenv("KUKANILEA_ENV", "test")
    assert _clamav_optional_enabled() is True
