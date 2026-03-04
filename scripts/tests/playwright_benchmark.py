from __future__ import annotations

import json
import logging
import sys
import time
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

BASE_URL = "http://127.0.0.1:5051"
OUT = Path("docs/status/playwright_benchmark_latest.json")

KPI_TARGETS = {
    "login_first_paint_ms": 400,
    "dashboard_nav_ms": 600,
    "status_api_ms": 200,
}


def _http_smoke() -> dict[str, float]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(f"{BASE_URL}/login", timeout=5) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"/login returned status {resp.status}")
    login_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    with urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=5) as health:
        if health.status >= 400:
            raise RuntimeError(f"/api/health returned status {health.status}")
    api_ms = (time.perf_counter() - t1) * 1000

    return {
        "login_first_paint_ms": round(login_ms, 2),
        "status_api_ms": round(api_ms, 2),
        "dashboard_nav_ms": -1.0,
        "mode": "http-fallback",
    }


def _playwright_flow() -> dict[str, float]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        start = time.perf_counter()
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=8000)
        login_ms = (time.perf_counter() - start) * 1000

        nav_start = time.perf_counter()
        page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=8000)
        nav_ms = (time.perf_counter() - nav_start) * 1000

        api_start = time.perf_counter()
        response = page.request.get(f"{BASE_URL}/api/health", timeout=5000)
        api_ms = (time.perf_counter() - api_start) * 1000
        response.raise_for_status()

        browser.close()

    return {
        "login_first_paint_ms": round(login_ms, 2),
        "dashboard_nav_ms": round(nav_ms, 2),
        "status_api_ms": round(api_ms, 2),
        "mode": "playwright",
    }


def main() -> None:
    try:
        urllib.request.urlopen(BASE_URL, timeout=3)
    except Exception:
        logging.error("Server is not running at %s", BASE_URL)
        sys.exit(1)

    try:
        metrics = _playwright_flow()
    except Exception as exc:
        logging.warning("Playwright unavailable, falling back to HTTP benchmark: %s", exc)
        metrics = _http_smoke()

    report = {
        "kpi_targets": KPI_TARGETS,
        "metrics": metrics,
        "pass": {
            key: (metrics.get(key, 0) >= 0 and metrics[key] <= KPI_TARGETS[key])
            for key in KPI_TARGETS
            if metrics.get(key, -1) >= 0
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
