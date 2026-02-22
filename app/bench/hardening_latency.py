from __future__ import annotations

import json
import os
import platform
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from app import create_app
from app.auth import hash_password
from app.db import AuthDB

DEFAULT_THRESHOLDS: dict[str, dict[str, dict[str, Any]]] = {
    "dev": {
        "ai_p95_ms": {"max": 2000.0, "severity": "warn"},
        "search_p95_ms": {"max": 800.0, "severity": "warn"},
    },
    "ci": {
        "ai_p95_ms": {"max": 2200.0, "severity": "fail"},
        "search_p95_ms": {"max": 900.0, "severity": "fail"},
    },
}


def _percentile(samples: list[float], q: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))
    return float(ordered[idx])


def _mock_ai_process_message(**kwargs):
    user_message = str(kwargs.get("user_message") or "")
    if "search" in user_message.lower() or "suche" in user_message.lower():
        return {
            "status": "ok",
            "response": "Mock: Suche erfolgreich.",
            "conversation_id": "bench-hardening-conv-search",
            "tool_used": ["search_contacts"],
        }
    return {
        "status": "ok",
        "response": "Mock: Antwort erfolgreich.",
        "conversation_id": "bench-hardening-conv-text",
        "tool_used": [],
    }


@contextmanager
def _isolated_env():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_dir = Path(tmp).resolve()
        old = {
            "HOME": os.environ.get("HOME"),
            "KUKANILEA_AUTH_DB": os.environ.get("KUKANILEA_AUTH_DB"),
            "DB_FILENAME": os.environ.get("DB_FILENAME"),
            "BASE_DIRNAME": os.environ.get("BASE_DIRNAME"),
            "OLLAMA_HOST": os.environ.get("OLLAMA_HOST"),
            "OLLAMA_TIMEOUT": os.environ.get("OLLAMA_TIMEOUT"),
        }
        os.environ["HOME"] = str(tmp_dir)
        os.environ["KUKANILEA_AUTH_DB"] = str(tmp_dir / "auth.db")
        os.environ["DB_FILENAME"] = str(tmp_dir / "core.db")
        os.environ["BASE_DIRNAME"] = "Kukanilea_Hardening_Bench"
        os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
        os.environ["OLLAMA_TIMEOUT"] = "1"
        try:
            yield
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _seed_auth(auth_db: AuthDB) -> None:
    now = "2026-02-21T00:00:00"
    auth_db.upsert_tenant("KUKANILEA", "KUKANILEA", now)
    auth_db.upsert_user("bench", hash_password("bench"), now)
    auth_db.upsert_membership("bench", "KUKANILEA", "DEV", now)


def run_latency_suite(
    requests_count: int = 30, use_real_ai: bool = False
) -> dict[str, Any]:
    req_count = max(1, int(requests_count))
    with _isolated_env():
        app = create_app()
        app.config.update(TESTING=True, READ_ONLY=False)
        with app.app_context():
            auth_db: AuthDB = app.extensions["auth_db"]
            _seed_auth(auth_db)

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["user"] = "bench"
            sess["role"] = "DEV"
            sess["tenant_id"] = "KUKANILEA"

        # Seed one searchable knowledge note.
        seed = client.post(
            "/api/knowledge/notes",
            json={"title": "Latency Seed Note", "body": "Hardening benchmark seed"},
        )
        if seed.status_code != 200:
            raise RuntimeError(f"knowledge seed failed: HTTP {seed.status_code}")

        ai_lat_ms: list[float] = []
        search_lat_ms: list[float] = []
        ai_errors = 0
        search_errors = 0

        def _run_once(i: int) -> None:
            nonlocal ai_errors, search_errors
            q = "Suche Kontakt" if i % 2 == 0 else "Kurze Zusammenfassung"

            t0 = time.perf_counter()
            ai_resp = client.post("/api/ai/chat", json={"q": q})
            ai_lat_ms.append((time.perf_counter() - t0) * 1000.0)
            if ai_resp.status_code != 200:
                ai_errors += 1

            t1 = time.perf_counter()
            search_resp = client.get("/api/knowledge/search?q=Latency%20Seed")
            search_lat_ms.append((time.perf_counter() - t1) * 1000.0)
            if search_resp.status_code != 200:
                search_errors += 1

        if use_real_ai:
            for idx in range(req_count):
                _run_once(idx)
        else:
            with patch(
                "app.web.ai_process_message", side_effect=_mock_ai_process_message
            ):
                for idx in range(req_count):
                    _run_once(idx)

    return {
        "mode": "real_ai" if use_real_ai else "mock_ai",
        "requests": req_count,
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "ai_chat": {
            "errors": ai_errors,
            "p50_ms": round(_percentile(ai_lat_ms, 0.50), 3),
            "p95_ms": round(_percentile(ai_lat_ms, 0.95), 3),
            "avg_ms": round(sum(ai_lat_ms) / max(1, len(ai_lat_ms)), 3),
        },
        "search": {
            "errors": search_errors,
            "p50_ms": round(_percentile(search_lat_ms, 0.50), 3),
            "p95_ms": round(_percentile(search_lat_ms, 0.95), 3),
            "avg_ms": round(sum(search_lat_ms) / max(1, len(search_lat_ms)), 3),
        },
    }


def load_thresholds(
    path: str | Path | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    if not path:
        return dict(DEFAULT_THRESHOLDS)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return dict(DEFAULT_THRESHOLDS)
    return payload


def evaluate_thresholds(
    report: dict[str, Any],
    thresholds: dict[str, dict[str, dict[str, Any]]],
    profile: str = "dev",
) -> dict[str, Any]:
    profile_key = str(profile or "dev").strip().lower()
    selected = thresholds.get(profile_key) or thresholds.get("dev") or {}
    checks: list[dict[str, Any]] = []
    fail_count = 0
    warn_count = 0
    metric_values = {
        "ai_p95_ms": float((report.get("ai_chat") or {}).get("p95_ms") or 0.0),
        "search_p95_ms": float((report.get("search") or {}).get("p95_ms") or 0.0),
    }
    for metric, rule in selected.items():
        limit = float((rule or {}).get("max") or 0.0)
        severity = str((rule or {}).get("severity") or "warn").strip().lower()
        value = float(metric_values.get(metric, 0.0))
        exceeded = value > limit if limit > 0 else False
        status = "PASS"
        if exceeded and severity == "fail":
            status = "FAIL"
            fail_count += 1
        elif exceeded:
            status = "WARN"
            warn_count += 1
        checks.append(
            {
                "metric": metric,
                "value": round(value, 3),
                "max": round(limit, 3),
                "severity": severity,
                "status": status,
            }
        )
    return {
        "profile": profile_key,
        "checks": checks,
        "warn_count": warn_count,
        "fail_count": fail_count,
    }
