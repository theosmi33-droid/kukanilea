from __future__ import annotations

import argparse
import json


def _human_report(result: dict) -> str:
    lines = [
        "OCR Devtools Test",
        f"tenant: {result.get('tenant_id')}",
        f"sandbox: {bool(result.get('sandbox'))}",
        f"ok: {bool(result.get('ok'))}",
        f"reason: {result.get('reason') or '-'}",
        f"policy_enabled: {bool(result.get('policy_enabled'))}",
        f"tesseract_found: {bool(result.get('tesseract_found'))}",
        f"read_only: {bool(result.get('read_only'))}",
        f"job_status: {result.get('job_status') or '-'}",
        f"job_error_code: {result.get('job_error_code') or '-'}",
        f"duration_ms: {result.get('duration_ms') if result.get('duration_ms') is not None else '-'}",
        f"chars_out: {result.get('chars_out') if result.get('chars_out') is not None else '-'}",
        f"truncated: {bool(result.get('truncated'))}",
        f"pii_found_knowledge: {bool(result.get('pii_found_knowledge'))}",
        f"pii_found_eventlog: {bool(result.get('pii_found_eventlog'))}",
        f"message: {result.get('message') or '-'}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OCR pipeline verification test")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--no-sandbox", action="store_true")
    parser.add_argument("--keep-artifacts", action="store_true")
    args = parser.parse_args()

    try:
        # Lazy import keeps sandbox env wiring possible before heavy modules.
        from app.devtools.ocr_test import run_ocr_test

        result = run_ocr_test(
            args.tenant,
            timeout_s=max(1, int(args.timeout)),
            sandbox=not bool(args.no_sandbox),
            keep_artifacts=bool(args.keep_artifacts),
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "reason": "unexpected_error",
            "message": type(exc).__name__,
        }
        print(json.dumps(payload, sort_keys=True))
        return 3

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(_human_report(result))
    return 0 if bool(result.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
