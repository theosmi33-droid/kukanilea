#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = "python3"
PORT = 5051
BASE_URL = f"http://127.0.0.1:{PORT}"
COLD_START_BUDGET_MS = 12000
PAGE_BUDGET_MS = 1500
PAGES = ["/", "/dashboard", "/messenger"]


def wait_http(timeout_s: float = 30.0) -> float:
    start = time.perf_counter()
    deadline = start + timeout_s
    while time.perf_counter() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/", timeout=1.0) as resp:
                if resp.status in (200, 302):
                    return (time.perf_counter() - start) * 1000
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("server readiness timeout")


def measure_playwright() -> dict[str, float]:
    from playwright.sync_api import sync_playwright

    results: dict[str, float] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for path in PAGES:
            t0 = time.perf_counter()
            page.goto(BASE_URL + path, wait_until="domcontentloaded")
            results[path] = (time.perf_counter() - t0) * 1000
        browser.close()
    return results


def main() -> int:
    proc = subprocess.Popen(
        [PYTHON, "kukanilea_app.py", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    report: dict[str, object] = {}
    try:
        cold_start_ms = wait_http()
        report["cold_start_ms"] = round(cold_start_ms, 2)
        page_times = measure_playwright()
        report["page_render_ms"] = {k: round(v, 2) for k, v in page_times.items()}

        failed = []
        if cold_start_ms > COLD_START_BUDGET_MS:
            failed.append(f"cold_start_ms>{COLD_START_BUDGET_MS}")
        for path, value in page_times.items():
            if value > PAGE_BUDGET_MS:
                failed.append(f"{path}>{PAGE_BUDGET_MS}ms")

        out = ROOT / "docs" / "status" / "PERFORMANCE_GATE_LAST.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print(json.dumps(report, indent=2))
        if failed:
            print("[PERF] FAILED: " + ", ".join(failed))
            return 1
        print("[PERF] PASSED")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
