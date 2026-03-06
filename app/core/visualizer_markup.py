from __future__ import annotations

import csv
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

try:
    import openpyxl  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    openpyxl = None


TOTAL_HINTS = ("total", "sum", "subtotal", "gesamt", "summe")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(raw: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (raw or "").strip()).strip("-").lower()
    return cleaned or fallback


def markup_storage_path(base_dir: Path, tenant_id: str, project_id: str) -> Path:
    tenant = _safe_id(tenant_id, "default")
    project = _safe_id(project_id, "default")
    return base_dir / "visualizer_markup" / tenant / f"{project}.json"


def empty_markup_document(tenant_id: str, project_id: str) -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": 1,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "created_at": now,
        "updated_at": now,
        "anchors": [],
        "notes": [],
        "highlights": [],
    }


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def validate_markup_payload(payload: dict[str, Any]) -> dict[str, Any]:
    page = int(payload.get("page") or 0)
    x = _as_float(payload.get("x"), 0.0)
    y = _as_float(payload.get("y"), 0.0)
    note = str(payload.get("note") or "").strip()
    if page < 0:
        raise ValueError("page must be >= 0")
    if x < 0 or y < 0:
        raise ValueError("anchor coordinates must be >= 0")

    highlight_raw = payload.get("highlight") or {}
    if highlight_raw and not isinstance(highlight_raw, dict):
        raise ValueError("highlight must be an object")
    highlight = {
        "x": _as_float(highlight_raw.get("x"), x),
        "y": _as_float(highlight_raw.get("y"), y),
        "width": max(0.0, _as_float(highlight_raw.get("width"), 0.0)),
        "height": max(0.0, _as_float(highlight_raw.get("height"), 0.0)),
        "color": str(highlight_raw.get("color") or "#ffeb3b")[:24],
    }
    return {"page": page, "x": x, "y": y, "note": note, "highlight": highlight}


def load_markup_document(base_dir: Path, tenant_id: str, project_id: str) -> dict[str, Any]:
    path = markup_storage_path(base_dir, tenant_id, project_id)
    if not path.exists():
        return empty_markup_document(tenant_id, project_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return empty_markup_document(tenant_id, project_id)
    return data


def append_markup(base_dir: Path, tenant_id: str, project_id: str, source: str, payload: dict[str, Any]) -> dict[str, Any]:
    doc = load_markup_document(base_dir, tenant_id, project_id)
    sanitized = validate_markup_payload(payload)
    now = _utc_now()

    anchor_id = f"a-{int(time.time() * 1000)}-{len(doc.get('anchors', [])) + 1}"
    note_id = f"n-{anchor_id}"
    hl_id = f"h-{anchor_id}"

    anchor = {
        "id": anchor_id,
        "source": source,
        "page": sanitized["page"],
        "x": sanitized["x"],
        "y": sanitized["y"],
        "created_at": now,
    }
    note = {
        "id": note_id,
        "anchor_id": anchor_id,
        "text": sanitized["note"],
        "created_at": now,
    }
    highlight = {
        "id": hl_id,
        "anchor_id": anchor_id,
        "source": source,
        "page": sanitized["page"],
        **sanitized["highlight"],
        "created_at": now,
    }

    doc.setdefault("anchors", []).append(anchor)
    if sanitized["note"]:
        doc.setdefault("notes", []).append(note)
    doc.setdefault("highlights", []).append(highlight)
    doc["updated_at"] = now

    path = markup_storage_path(base_dir, tenant_id, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"anchor": anchor, "note": note if sanitized["note"] else None, "highlight": highlight, "storage_path": str(path)}


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)) and math.isfinite(float(v)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        out = float(s)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _read_table(fp: Path, max_rows: int = 2000) -> tuple[list[str], list[list[Any]]]:
    ext = fp.suffix.lower()
    if ext == ".csv":
        with fp.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return [], []
        return [str(x).strip() for x in rows[0]], rows[1 : max_rows + 1]

    if ext == ".xlsx":
        if openpyxl is None:
            raise RuntimeError("openpyxl unavailable")
        wb = openpyxl.load_workbook(str(fp), read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        header_row = next(it, None)
        headers = [str(v).strip() if v is not None else "" for v in (header_row or [])]
        rows = []
        for idx, row in enumerate(it):
            if idx >= max_rows:
                break
            rows.append(list(row))
        return headers, rows

    raise ValueError("unsupported file type")


def analyze_excel_summary(fp: Path, max_rows: int = 2000) -> dict[str, Any]:
    headers, rows = _read_table(fp, max_rows=max_rows)
    if not headers:
        return {"rows": 0, "columns": 0, "totals": [], "anomalies": [], "missing_fields": []}

    numeric_by_col: dict[int, list[float]] = {}
    for row in rows:
        for c, value in enumerate(row[: len(headers)]):
            n = _to_float(value)
            if n is not None:
                numeric_by_col.setdefault(c, []).append(n)

    totals: list[dict[str, Any]] = []
    for r_idx, row in enumerate(rows):
        row_text = " ".join(str(v or "").lower() for v in row)
        row_is_total = any(h in row_text for h in TOTAL_HINTS)
        if not row_is_total:
            continue
        for c, value in enumerate(row[: len(headers)]):
            n = _to_float(value)
            if n is None:
                continue
            prev_values = [_to_float(rr[c]) for rr in rows[:r_idx] if c < len(rr)]
            prev_num = [x for x in prev_values if x is not None]
            if len(prev_num) >= 2 and abs(sum(prev_num) - n) <= max(0.01, abs(n) * 0.01):
                totals.append({"row": r_idx + 2, "column": headers[c], "value": n, "match": "sum_of_above"})

    anomalies: list[dict[str, Any]] = []
    for c, values in numeric_by_col.items():
        if len(values) < 4:
            continue
        sorted_vals = sorted(values)
        median = sorted_vals[len(sorted_vals) // 2]
        mu = mean(values)
        sigma = pstdev(values)
        lo, hi = mu - (3.0 * sigma), mu + (3.0 * sigma)
        ratio_limit = abs(median) * 10 if median else None
        for r_idx, row in enumerate(rows):
            if c >= len(row):
                continue
            n = _to_float(row[c])
            if n is None:
                continue
            is_sigma_outlier = sigma > 0 and (n < lo or n > hi)
            is_ratio_outlier = ratio_limit is not None and abs(n) > ratio_limit
            if is_sigma_outlier or is_ratio_outlier:
                anomalies.append({"row": r_idx + 2, "column": headers[c], "value": n, "kind": "outlier"})

    missing_fields = []
    for c, header in enumerate(headers):
        missing = 0
        for row in rows:
            if c >= len(row) or row[c] in (None, ""):
                missing += 1
        if missing:
            missing_fields.append({"column": header or f"col_{c+1}", "missing": missing})

    return {
        "rows": len(rows),
        "columns": len(headers),
        "totals": totals,
        "anomalies": anomalies[:50],
        "missing_fields": missing_fields,
    }
