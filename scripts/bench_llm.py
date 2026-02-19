#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _percentile(samples: list[float], q: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))
    return float(ordered[idx])


def _mock_ai_process_message(**kwargs):
    user_message = str(kwargs.get("user_message") or "")
    if "suche" in user_message.lower():
        return {
            "status": "ok",
            "response": "Mock: 3 Kontakte gefunden.",
            "conversation_id": "bench-conv-tool",
            "tool_used": ["search_contacts"],
        }
    return {
        "status": "ok",
        "response": "Mock: Antwort ohne Tool-Use.",
        "conversation_id": "bench-conv-text",
        "tool_used": [],
    }


def run_benchmark(requests_count: int, use_real_ai: bool) -> dict[str, float | int]:
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True, READ_ONLY=False)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "bench"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    latencies_ms: list[float] = []
    ok_count = 0
    error_count = 0

    def _run_once(i: int) -> None:
        nonlocal ok_count, error_count
        query = "Suche nach Mueller" if i % 2 == 0 else "Kurze Zusammenfassung"
        started = time.perf_counter()
        response = client.post("/api/ai/chat", json={"q": query})
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(elapsed_ms)
        if response.status_code == 200:
            ok_count += 1
        else:
            error_count += 1

    if use_real_ai:
        for idx in range(max(1, int(requests_count))):
            _run_once(idx)
    else:
        with patch("app.web.ai_process_message", side_effect=_mock_ai_process_message):
            for idx in range(max(1, int(requests_count))):
                _run_once(idx)

    total_ms = float(sum(latencies_ms))
    return {
        "requests": len(latencies_ms),
        "ok_count": ok_count,
        "error_count": error_count,
        "total_ms": round(total_ms, 3),
        "p50_ms": round(_percentile(latencies_ms, 0.50), 3),
        "p95_ms": round(_percentile(latencies_ms, 0.95), 3),
        "p99_ms": round(_percentile(latencies_ms, 0.99), 3),
        "avg_ms": round(total_ms / max(1, len(latencies_ms)), 3),
        "mode": "real_ai" if use_real_ai else "mock_ai",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark AI chat endpoint latency with mock or real AI."
    )
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--real-ai", action="store_true")
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()

    report = run_benchmark(requests_count=args.requests, use_real_ai=args.real_ai)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
