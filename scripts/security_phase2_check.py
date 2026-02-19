#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path


def _core_db_path() -> Path:
    env = os.environ.get("KUKANILEA_CORE_DB", "").strip()
    if env:
        return Path(env)
    return (
        Path.home() / "Library" / "Application Support" / "KUKANILEA" / "core.sqlite3"
    )


def _count_eventlog_pii_hits(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute(
            """
            SELECT COUNT(*)
            FROM events
            WHERE payload_json LIKE '%@%'
               OR LOWER(payload_json) LIKE '%email%'
               OR LOWER(payload_json) LIKE '%phone%'
               OR LOWER(payload_json) LIKE '%iban%'
            """
        ).fetchone()
        return int((row or [0])[0] or 0)
    finally:
        con.close()


def _scan_source_for_plaintext_password_tokens(repo_root: Path) -> int:
    pattern = re.compile(r"password\\s*=", re.IGNORECASE)
    excluded = {"venv", ".venv", ".git", "dist", "build", "__pycache__"}
    hits = 0
    for path in repo_root.rglob("*.py"):
        if any(part in excluded for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            line_norm = line.lower()
            if "encrypted" in line_norm or "get_encryption_key" in line_norm:
                continue
            if pattern.search(line):
                hits += 1
    return hits


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    db_path = _core_db_path()
    eventlog_hits = _count_eventlog_pii_hits(db_path)
    password_hits = _scan_source_for_plaintext_password_tokens(repo_root)

    report = {
        "core_db": str(db_path),
        "eventlog_pii_hits": eventlog_hits,
        "plaintext_password_token_hits": password_hits,
        "ok": eventlog_hits == 0,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
