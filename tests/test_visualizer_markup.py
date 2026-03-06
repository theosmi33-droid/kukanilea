from __future__ import annotations

import time
from pathlib import Path

from app.core.visualizer_markup import analyze_excel_summary, append_markup, load_markup_document, validate_markup_payload


def test_validate_markup_payload_rejects_negative_anchor() -> None:
    try:
        validate_markup_payload({"page": 0, "x": -1, "y": 5})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "coordinates" in str(exc)


def test_markup_storage_roundtrip(tmp_path: Path) -> None:
    result = append_markup(
        base_dir=tmp_path,
        tenant_id="tenant-A",
        project_id="Project 1",
        source="doc://sample.pdf",
        payload={"page": 2, "x": 120.5, "y": 77.0, "note": "Check amount", "highlight": {"x": 100, "y": 70, "width": 80, "height": 12}},
    )
    assert result["anchor"]["page"] == 2
    stored = load_markup_document(tmp_path, tenant_id="tenant-A", project_id="Project 1")
    assert len(stored["anchors"]) == 1
    assert len(stored["notes"]) == 1
    assert len(stored["highlights"]) == 1


def test_excel_analyzer_detects_totals_missing_and_anomalies(tmp_path: Path) -> None:
    fp = tmp_path / "sheet.csv"
    fp.write_text(
        "item,amount,qty\n"
        "A,10,1\n"
        "B,20,1\n"
        "C,30,1\n"
        "D,40,1\n"
        "E,,1\n"
        "F,5000,1\n"
        "Total,5100,6\n",
        encoding="utf-8",
    )
    out = analyze_excel_summary(fp)
    assert out["rows"] == 7
    assert any(x["column"] == "amount" for x in out["missing_fields"])
    assert out["totals"], "expected total detection"
    assert out["anomalies"], "expected anomaly detection"


def test_excel_analyzer_performance_sanity(tmp_path: Path) -> None:
    fp = tmp_path / "large.csv"
    lines = ["name,amount"] + [f"r{i},{i % 97}" for i in range(2000)] + ["Total,96084"]
    fp.write_text("\n".join(lines), encoding="utf-8")
    start = time.perf_counter()
    out = analyze_excel_summary(fp)
    elapsed = time.perf_counter() - start
    assert out["rows"] >= 2000
    assert elapsed < 1.0
