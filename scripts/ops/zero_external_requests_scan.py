#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = [ROOT / "app/templates", ROOT / "static", ROOT / "app/static"]
TEXT_SUFFIXES = {".html", ".js", ".css"}
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "www.w3.org"}

HTML_ATTR_URL_RE = re.compile(r"(?:src|href|action)=[\"'](https?://[^\"']+)[\"']", re.IGNORECASE)
CSS_URL_RE = re.compile(r"url\([\"']?(https?://[^\)\"']+)[\"']?\)", re.IGNORECASE)
JS_NET_RE = re.compile(
    r"(?:fetch|axios\.(?:get|post|put|patch|delete)|XMLHttpRequest\s*\(\)|new\s+WebSocket)"
    r"[^\n]{0,120}?['\"](https?://[^'\"]+)['\"]",
    re.IGNORECASE,
)


def host_from_url(url: str) -> str:
    m = re.match(r"https?://([^/:]+)", url)
    return (m.group(1).lower() if m else "")


def should_scan(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def matches_for_line(path: Path, line: str) -> list[str]:
    out: list[str] = []
    if path.suffix.lower() == ".html":
        out.extend(HTML_ATTR_URL_RE.findall(line))
    elif path.suffix.lower() == ".css":
        out.extend(CSS_URL_RE.findall(line))
    else:
        out.extend(JS_NET_RE.findall(line))
    return out


def main() -> int:
    violations: list[str] = []
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for file in base.rglob("*"):
            if not file.is_file() or not should_scan(file):
                continue
            rel = file.relative_to(ROOT)
            content = file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line_num, line in enumerate(content, start=1):
                for url in matches_for_line(file, line):
                    host = host_from_url(url)
                    if host and host not in ALLOWED_HOSTS:
                        violations.append(f"{rel}:{line_num} external_runtime_url={url}")

    if violations:
        print("[SECURITY] ZERO EXTERNAL REQUESTS GATE: FAILED")
        for v in violations:
            print(f"- {v}")
        return 1

    print("[SECURITY] ZERO EXTERNAL REQUESTS GATE: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
