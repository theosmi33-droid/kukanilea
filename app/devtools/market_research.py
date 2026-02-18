from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REQUIRED_COLUMNS = {
    "tool",
    "category",
    "priority",
    "deployment",
    "open_source",
    "source_url",
    "snapshot_date",
}
HIGH_PRIORITY_REQUIRED_NONEMPTY = {
    "deployment",
    "offline",
    "multi_tenant",
    "source_url",
    "snapshot_date",
}
VALID_PRIORITIES = {"high", "medium", "low"}


def _load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = [
            {str(k or ""): str(v or "").strip() for k, v in row.items()}
            for row in reader
        ]
    return header, rows


def validate_matrix(path: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return {
            "ok": False,
            "errors": [f"matrix_missing:{path}"],
            "warnings": [],
            "rows": 0,
        }

    header, rows = _load_rows(path)
    missing = sorted(REQUIRED_COLUMNS - set(header))
    if missing:
        errors.append("missing_columns:" + ",".join(missing))

    for idx, row in enumerate(rows, start=2):
        tool = row.get("tool", "")
        if not tool:
            errors.append(f"row_{idx}:tool_missing")
            continue

        priority = row.get("priority", "").strip().lower()
        if priority and priority not in VALID_PRIORITIES:
            errors.append(f"row_{idx}:{tool}:invalid_priority:{priority}")

        if priority == "high":
            for field in sorted(HIGH_PRIORITY_REQUIRED_NONEMPTY):
                if not str(row.get(field, "")).strip():
                    warnings.append(f"row_{idx}:{tool}:missing_{field}")

        source_url = str(row.get("source_url", "")).strip()
        if source_url and not (
            source_url.startswith("http://") or source_url.startswith("https://")
        ):
            errors.append(f"row_{idx}:{tool}:invalid_source_url")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "rows": len(rows),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate competitor research matrix")
    parser.add_argument(
        "--matrix",
        default="docs/market_research/competitor_matrix.csv",
        help="Path to competitor matrix CSV",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if warnings exist",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = validate_matrix(Path(args.matrix))

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"ok={report['ok']} rows={report['rows']}")
        if report["errors"]:
            print("errors:")
            for item in report["errors"]:
                print(f"- {item}")
        if report["warnings"]:
            print("warnings:")
            for item in report["warnings"]:
                print(f"- {item}")

    if not bool(report["ok"]):
        return 1
    if args.strict and bool(report["warnings"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
