#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import os
import psutil
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

def get_ollama_memory():
    total_rss = 0
    try:
        for proc in psutil.process_iter(['name', 'memory_info']):
            if 'ollama' in (proc.info['name'] or "").lower():
                total_rss += proc.info['memory_info'].rss
    except: pass
    return total_rss / (1024 * 1024) # MB

def run_benchmark(requests_count: int, use_real_ai: bool) -> dict[str, float | int]:
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True, READ_ONLY=False)
    client = app.test_client()
    
    with client.session_transaction() as sess:
        sess["user"] = "bench-user"
        sess["role"] = "ADMIN"
        sess["tenant_id"] = "KUKANILEA"

    latencies_ms: list[float] = []
    mem_samples: list[float] = []
    ok_count = 0
    error_count = 0

    print(f"Starting Benchmark: {requests_count} requests, real_ai={use_real_ai}")
    
    for idx in range(max(1, int(requests_count))):
        query = "Wer ist der Kunde Müller?" if idx % 2 == 0 else "Schreib einen Einzeiler über das Handwerk."
        started = time.perf_counter()
        
        response = client.post("/api/ai/chat", json={"msg": query}, headers={"X-Requested-With": "XMLHttpRequest"})
        
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(elapsed_ms)
        mem_samples.append(get_ollama_memory())
        
        if response.status_code == 200:
            ok_count += 1
            print(f"  [{idx+1}/{requests_count}] OK ({elapsed_ms/1000.0:.2f}s)")
        else:
            error_count += 1
            print(f"  [{idx+1}/{requests_count}] FAIL ({response.status_code}): {response.text[:100]}")

    total_ms = float(sum(latencies_ms))
    return {
        "requests": len(latencies_ms),
        "ok_count": ok_count,
        "error_count": error_count,
        "total_ms": round(total_ms, 3),
        "p50_ms": round(_percentile(latencies_ms, 0.50), 3),
        "p95_ms": round(_percentile(latencies_ms, 0.95), 3),
        "avg_ms": round(total_ms / max(1, len(latencies_ms)), 3),
        "mem_avg_mb": round(sum(mem_samples) / max(1, len(mem_samples)), 2),
        "mem_max_mb": round(max(mem_samples or [0]), 2),
        "mode": "real_ai" if use_real_ai else "mock_ai",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="KUKANILEA Gold AI Benchmark")
    parser.add_argument("--requests", type=int, default=5)
    parser.add_argument("--real-ai", action="store_true", default=True)
    args = parser.parse_args()

    report = run_benchmark(requests_count=args.requests, use_real_ai=args.real_ai)
    print("\n--- BENCHMARK REPORT ---")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    main()
