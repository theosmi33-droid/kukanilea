#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _percentile(samples: list[float], q: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))
    return float(ordered[idx])


def run_benchmark(docs: int) -> dict[str, float | int]:
    from app.knowledge.core import knowledge_redact_text

    latencies_ms: list[float] = []
    base = (
        "Rechnung fuer Max Mustermann, max@demo.invalid, +49 000 1234567, "
        "IBAN DE00123456780000111122, Frist 14 Tage."
    )
    for idx in range(max(1, int(docs))):
        payload = f"{base} Dokument {idx}"
        started = time.perf_counter()
        _ = knowledge_redact_text(payload)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(elapsed_ms)

    total_ms = float(sum(latencies_ms))
    return {
        "docs": len(latencies_ms),
        "total_ms": round(total_ms, 3),
        "p50_ms": round(_percentile(latencies_ms, 0.50), 3),
        "p95_ms": round(_percentile(latencies_ms, 0.95), 3),
        "p99_ms": round(_percentile(latencies_ms, 0.99), 3),
        "avg_ms": round(total_ms / max(1, len(latencies_ms)), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark synthetic OCR-redaction path over N documents."
    )
    parser.add_argument("--docs", type=int, default=100)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    report = run_benchmark(docs=args.docs)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
