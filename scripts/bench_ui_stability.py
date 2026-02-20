#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional
    sync_playwright = None

HTML_ROUTES = [
    "/",
    "/tasks",
    "/time",
    "/assistant",
    "/chat",
    "/postfach",
    "/crm/customers",
    "/leads/inbox",
    "/knowledge",
    "/workflows",
    "/automation",
    "/autonomy/health",
    "/insights/daily",
    "/settings",
]

API_ROUTES = [
    "/api/health/live",
    "/api/ai/status",
    "/api/tasks",
    "/api/time/entries",
]

JSON_BLOB_RE = re.compile(r'^\s*\{\s*"ok"\s*:\s*false', re.I)


@dataclass
class Stats:
    started_at: float
    lock: threading.Lock = field(default_factory=threading.Lock)
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    latencies_ms: list[float] = field(default_factory=list)
    per_route: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    failures: list[dict[str, Any]] = field(default_factory=list)

    def inc(self, key: str, amount: int = 1) -> None:
        with self.lock:
            self.counters[key] += amount

    def add_latency(self, value_ms: float) -> None:
        with self.lock:
            self.latencies_ms.append(value_ms)

    def add_route(self, route: str, key: str) -> None:
        with self.lock:
            self.per_route[route][key] += 1

    def add_failure(
        self, where: str, route: str, reason: str, status: int | None = None
    ) -> None:
        with self.lock:
            if len(self.failures) < 200:
                self.failures.append(
                    {
                        "t": round(time.time() - self.started_at, 3),
                        "where": where,
                        "route": route,
                        "reason": reason,
                        "status": status,
                    }
                )


def _login(base_url: str, username: str, password: str) -> requests.Session:
    s = requests.Session()
    s.get(base_url + "/login", timeout=10)
    r = s.post(
        base_url + "/login",
        data={"username": username, "password": password},
        allow_redirects=True,
        timeout=10,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"login failed status={r.status_code}")
    return s


def _html_worker(
    worker_id: int,
    base_url: str,
    username: str,
    password: str,
    end_ts: float,
    stats: Stats,
) -> None:
    try:
        s = _login(base_url, username, password)
    except Exception as exc:
        stats.inc("worker_login_fail")
        stats.add_failure("html", "/login", f"login_fail:{exc}")
        return

    while time.time() < end_ts:
        route = random.choice(HTML_ROUTES)
        t0 = time.perf_counter()
        try:
            r = s.get(base_url + route, headers={"Accept": "text/html"}, timeout=12)
            dt = (time.perf_counter() - t0) * 1000.0
            stats.inc("html_total")
            stats.add_latency(dt)
            stats.add_route(route, "total")
            if r.status_code >= 500:
                stats.inc("html_5xx")
                stats.add_route(route, "5xx")
                stats.add_failure("html", route, "http_5xx", r.status_code)
            elif r.status_code >= 400:
                stats.inc("html_4xx")
                stats.add_route(route, "4xx")
            body = r.text or ""
            has_shell = 'data-app-shell="1"' in body or 'id="appNav"' in body
            if not has_shell:
                stats.inc("html_missing_shell")
                stats.add_route(route, "missing_shell")
                stats.add_failure("html", route, "missing_shell", r.status_code)
            if JSON_BLOB_RE.search(body[:400]):
                stats.inc("html_json_blob")
                stats.add_route(route, "json_blob")
                stats.add_failure("html", route, "json_blob", r.status_code)
        except Exception as exc:
            stats.inc("html_exceptions")
            stats.add_route(route, "exception")
            stats.add_failure("html", route, f"exception:{type(exc).__name__}")


def _api_worker(
    worker_id: int,
    base_url: str,
    username: str,
    password: str,
    end_ts: float,
    stats: Stats,
) -> None:
    try:
        s = _login(base_url, username, password)
    except Exception as exc:
        stats.inc("worker_login_fail")
        stats.add_failure("api", "/login", f"login_fail:{exc}")
        return

    while time.time() < end_ts:
        route = random.choice(API_ROUTES)
        t0 = time.perf_counter()
        try:
            r = s.get(
                base_url + route, headers={"Accept": "application/json"}, timeout=12
            )
            dt = (time.perf_counter() - t0) * 1000.0
            stats.inc("api_total")
            stats.add_latency(dt)
            stats.add_route(route, "total")
            if r.status_code >= 500:
                stats.inc("api_5xx")
                stats.add_route(route, "5xx")
                stats.add_failure("api", route, "http_5xx", r.status_code)
            elif r.status_code >= 400:
                stats.inc("api_4xx")
                stats.add_route(route, "4xx")
            ctype = (r.headers.get("content-type") or "").lower()
            if "application/json" not in ctype:
                stats.inc("api_non_json")
                stats.add_route(route, "non_json")
                stats.add_failure("api", route, f"non_json:{ctype}", r.status_code)
            else:
                try:
                    r.json()
                except Exception:
                    stats.inc("api_bad_json")
                    stats.add_route(route, "bad_json")
                    stats.add_failure("api", route, "bad_json", r.status_code)
        except Exception as exc:
            stats.inc("api_exceptions")
            stats.add_route(route, "exception")
            stats.add_failure("api", route, f"exception:{type(exc).__name__}")


def _browser_worker(
    base_url: str, username: str, password: str, end_ts: float, stats: Stats
) -> None:
    if sync_playwright is None:
        stats.inc("browser_skipped")
        return
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(base_url + "/login", wait_until="domcontentloaded", timeout=15000)
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_load_state("domcontentloaded", timeout=15000)

            while time.time() < end_ts:
                route = random.choice(HTML_ROUTES)
                try:
                    page.goto(
                        base_url + route, wait_until="domcontentloaded", timeout=15000
                    )
                    stats.inc("browser_total")

                    if page.locator("#appNav").count() == 0:
                        stats.inc("browser_missing_nav")
                        stats.add_failure("browser", route, "missing_nav")
                    if page.locator("#goBack").count() == 0:
                        stats.inc("browser_missing_back")
                        stats.add_failure("browser", route, "missing_back")
                    if page.locator("#reloadPage").count() == 0:
                        stats.inc("browser_missing_reload")
                        stats.add_failure("browser", route, "missing_reload")

                    body_text = page.locator("body").inner_text(timeout=3000)
                    if JSON_BLOB_RE.search(body_text[:400]):
                        stats.inc("browser_json_blob")
                        stats.add_failure("browser", route, "json_blob")

                    if page.locator("#navCollapse").count() > 0:
                        page.click("#navCollapse")
                        page.click("#navCollapse")

                    if route != "/chat" and page.locator("#chatWidgetBtn").count() > 0:
                        page.click("#chatWidgetBtn", no_wait_after=True)
                        page.wait_for_selector("#chatDrawer:not(.hidden)", timeout=5000)
                        if page.locator("#chatWidgetInput").is_enabled():
                            page.fill("#chatWidgetInput", "hilfe")
                            page.click("#chatWidgetSend", no_wait_after=True)
                            page.wait_for_timeout(150)
                        if page.locator("#chatWidgetClose").count() > 0:
                            page.click("#chatWidgetClose", no_wait_after=True)

                    if page.locator("#goBack").count() > 0:
                        page.click("#goBack", no_wait_after=True)
                        page.wait_for_timeout(80)
                    if page.locator("#reloadPage").count() > 0:
                        page.click("#reloadPage", no_wait_after=True)
                        page.wait_for_load_state("domcontentloaded", timeout=15000)
                except Exception as exc:
                    stats.inc("browser_exceptions")
                    msg = str(exc).strip().replace("\n", " ")
                    stats.add_failure(
                        "browser",
                        route,
                        f"exception:{type(exc).__name__}:{msg[:220]}",
                    )
            ctx.close()
            browser.close()
    except Exception as exc:
        stats.inc("browser_init_fail")
        stats.add_failure("browser", "/", f"init_fail:{type(exc).__name__}:{exc}")


def _summary(stats: Stats, duration_s: int) -> dict[str, Any]:
    with stats.lock:
        lats = list(stats.latencies_ms)
        counters = dict(stats.counters)
        routes = {k: dict(v) for k, v in stats.per_route.items()}
        failures = list(stats.failures)

    p95 = None
    if lats:
        idx = min(len(lats) - 1, int(len(lats) * 0.95))
        p95 = round(sorted(lats)[idx], 2)

    return {
        "duration_seconds": duration_s,
        "counters": counters,
        "latency_ms": {
            "count": len(lats),
            "p50": round(statistics.median(lats), 2) if lats else None,
            "p95": p95,
            "max": round(max(lats), 2) if lats else None,
        },
        "per_route": routes,
        "failures_sample": failures,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--duration", type=int, default=1200)
    ap.add_argument("--html-workers", type=int, default=6)
    ap.add_argument("--api-workers", type=int, default=4)
    ap.add_argument("--browser", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    started = time.time()
    end_ts = started + args.duration
    stats = Stats(started_at=started)

    threads: list[threading.Thread] = []
    for i in range(args.html_workers):
        threads.append(
            threading.Thread(
                target=_html_worker,
                args=(
                    i,
                    args.base_url,
                    args.username,
                    args.password,
                    end_ts,
                    stats,
                ),
                daemon=True,
            )
        )
    for i in range(args.api_workers):
        threads.append(
            threading.Thread(
                target=_api_worker,
                args=(
                    i,
                    args.base_url,
                    args.username,
                    args.password,
                    end_ts,
                    stats,
                ),
                daemon=True,
            )
        )
    if args.browser:
        threads.append(
            threading.Thread(
                target=_browser_worker,
                args=(args.base_url, args.username, args.password, end_ts, stats),
                daemon=True,
            )
        )

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    result = _summary(stats, args.duration)
    Path(args.out).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    severe = result["counters"].get("html_5xx", 0)
    severe += result["counters"].get("html_missing_shell", 0)
    severe += result["counters"].get("html_json_blob", 0)
    severe += result["counters"].get("browser_missing_nav", 0)
    return 1 if severe > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
