from __future__ import annotations

from pathlib import Path

from app.devtools.market_research import validate_matrix


def test_validate_matrix_reports_missing_columns(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.csv"
    matrix.write_text("tool,category\nPaperless,DMS\n", encoding="utf-8")

    report = validate_matrix(matrix)
    assert report["ok"] is False
    errors = report.get("errors") or []
    assert any("missing_columns" in str(item) for item in errors)


def test_validate_matrix_warns_for_high_priority_gaps(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.csv"
    matrix.write_text(
        "tool,category,priority,deployment,open_source,source_url,snapshot_date,offline,multi_tenant\n"
        "Paperless,DMS,high,local,yes,,2026-02-18,,\n",
        encoding="utf-8",
    )

    report = validate_matrix(matrix)
    assert report["ok"] is True
    warnings = report.get("warnings") or []
    assert any("missing_source_url" in str(item) for item in warnings)
    assert any("missing_offline" in str(item) for item in warnings)
