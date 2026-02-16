from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _reason_message(reason: str | None) -> str:
    key = str(reason or "")
    if not key:
        return "OK"
    if key == "policy_denied":
        return "OCR policy is disabled for tenant."
    if key == "tesseract_missing":
        return "Tesseract binary not found or not allowlisted."
    if key == "tessdata_missing":
        return "Tesseract data files were not found."
    if key == "language_missing":
        return "Requested OCR language is unavailable."
    if key == "tesseract_failed":
        return "Tesseract execution failed."
    if key == "read_only":
        return "READ_ONLY active; skipping ingest/job run."
    if key == "pii_leak":
        return "PII leak detected in Knowledge or Eventlog."
    if key == "schema_unknown":
        return "Policy schema is unknown. Inspect existing_columns."
    if key == "ambiguous_columns":
        return "Multiple OCR policy columns detected; choose one explicitly."
    if key == "schema_unknown_insert":
        return "Policy row insert failed due to unknown required columns."
    if key == "watch_config_table_missing":
        return "Watch configuration table is missing in the selected database."
    if key == "source_files_table_missing":
        return "Source files table is missing in the selected database."
    if key == "source_files_schema_unknown":
        return "Source files lookup schema is unknown."
    if key == "failed":
        return "OCR command failed for the test image."
    if key == "timeout":
        return "OCR run timed out."
    if key == "job_not_found":
        return "No OCR job was detected within timeout."
    if key == "invalid_args":
        return "Invalid CLI argument combination."
    return "OCR test failed."


def _sanitize_path(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if text.startswith("/"):
        return "<path>"
    return text


def _status_enabled(status: dict[str, Any]) -> bool | None:
    if bool(status.get("ok")):
        return bool(status.get("policy_enabled"))
    return None


def _status_reason(status: dict[str, Any]) -> str | None:
    if bool(status.get("ok")):
        return None
    return str(status.get("reason") or "schema_unknown")


def _status_columns(status: dict[str, Any]) -> list[str] | None:
    columns = status.get("existing_columns")
    if columns is None:
        return None
    return [str(item) for item in list(columns)]


def _merge_policy_fields(
    result: dict[str, Any],
    *,
    base_status: dict[str, Any],
    effective_status: dict[str, Any],
) -> None:
    result["policy_enabled_base"] = _status_enabled(base_status)
    result["policy_enabled_effective"] = _status_enabled(effective_status)
    result["policy_reason"] = _status_reason(effective_status)
    result["existing_columns"] = _status_columns(effective_status)
    if result.get("existing_columns") is None:
        result["existing_columns"] = _status_columns(base_status)


def _policy_view_payload(
    *,
    tenant: str,
    status: dict[str, Any],
    next_actions: list[str],
) -> dict[str, Any]:
    reason = _status_reason(status)
    enabled = _status_enabled(status)
    return {
        "ok": bool(status.get("ok")),
        "reason": reason,
        "tenant_id": tenant,
        "sandbox": False,
        "policy_enabled": bool(enabled),
        "policy_enabled_base": enabled,
        "policy_enabled_effective": enabled,
        "policy_reason": reason,
        "existing_columns": _status_columns(status),
        "tesseract_found": False,
        "tessdata_dir": None,
        "tessdata_source": None,
        "tesseract_langs": [],
        "tesseract_lang_used": None,
        "tesseract_probe_reason": None,
        "tesseract_probe_next_actions": [],
        "tesseract_stderr_tail": None,
        "read_only": False,
        "job_status": None,
        "job_error_code": None,
        "pii_found_knowledge": False,
        "pii_found_eventlog": False,
        "duration_ms": None,
        "chars_out": None,
        "truncated": False,
        "sandbox_db_path": None,
        "watch_config_seeded": False,
        "watch_config_existed": None,
        "inbox_dir_used": None,
        "scanner_discovered_files": 0,
        "direct_submit_used": False,
        "source_lookup_reason": None,
        "source_files_columns": None,
        "next_actions": next_actions,
        "message": _reason_message(reason),
    }


def _human_report(result: dict) -> str:
    lines = [
        "OCR Devtools Test",
        f"tenant: {result.get('tenant_id')}",
        f"sandbox: {bool(result.get('sandbox'))}",
        f"ok: {bool(result.get('ok'))}",
        f"reason: {result.get('reason') or '-'}",
        f"policy_enabled: {bool(result.get('policy_enabled'))}",
        f"policy_enabled_base: {result.get('policy_enabled_base')}",
        f"policy_enabled_effective: {result.get('policy_enabled_effective')}",
        f"policy_reason: {result.get('policy_reason') or '-'}",
        f"existing_columns: {result.get('existing_columns') or '-'}",
        f"tesseract_found: {bool(result.get('tesseract_found'))}",
        f"tessdata_dir: {result.get('tessdata_dir') or '-'}",
        f"tessdata_source: {result.get('tessdata_source') or '-'}",
        f"tesseract_langs: {result.get('tesseract_langs') or '-'}",
        f"tesseract_lang_used: {result.get('tesseract_lang_used') or '-'}",
        f"tesseract_probe_reason: {result.get('tesseract_probe_reason') or '-'}",
        f"tesseract_stderr_tail: {result.get('tesseract_stderr_tail') or '-'}",
        f"read_only: {bool(result.get('read_only'))}",
        f"job_status: {result.get('job_status') or '-'}",
        f"job_error_code: {result.get('job_error_code') or '-'}",
        f"duration_ms: {result.get('duration_ms') if result.get('duration_ms') is not None else '-'}",
        f"chars_out: {result.get('chars_out') if result.get('chars_out') is not None else '-'}",
        f"truncated: {bool(result.get('truncated'))}",
        f"watch_config_seeded: {bool(result.get('watch_config_seeded'))}",
        f"watch_config_existed: {result.get('watch_config_existed')}",
        f"inbox_dir_used: {result.get('inbox_dir_used') or '-'}",
        f"scanner_discovered_files: {result.get('scanner_discovered_files')}",
        f"direct_submit_used: {bool(result.get('direct_submit_used'))}",
        f"pii_found_knowledge: {bool(result.get('pii_found_knowledge'))}",
        f"pii_found_eventlog: {bool(result.get('pii_found_eventlog'))}",
        f"sandbox_db_path: {result.get('sandbox_db_path') or '-'}",
        f"next_actions: {result.get('next_actions') or '-'}",
        f"message: {result.get('message') or '-'}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OCR pipeline verification test")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--show-policy", action="store_true")
    parser.add_argument("--show-tesseract", action="store_true")
    parser.add_argument("--enable-policy-in-sandbox", action="store_true")
    parser.add_argument("--no-sandbox", action="store_true")
    parser.add_argument("--tessdata-dir")
    parser.add_argument("--lang")
    parser.add_argument(
        "--seed-watch-config-in-sandbox",
        dest="seed_watch_config_in_sandbox",
        action="store_true",
    )
    parser.add_argument(
        "--no-seed-watch-config-in-sandbox",
        dest="seed_watch_config_in_sandbox",
        action="store_false",
    )
    parser.set_defaults(seed_watch_config_in_sandbox=True)
    parser.add_argument("--direct-submit-in-sandbox", action="store_true")
    parser.add_argument("--keep-artifacts", action="store_true")
    args = parser.parse_args()

    try:
        # Lazy import keeps sandbox env wiring possible before heavy modules.
        from app.devtools.ocr_policy import (
            enable_ocr_policy_in_db,
            get_policy_status,
        )
        from app.devtools.ocr_test import (
            detect_read_only,
            next_actions_for_reason,
            run_ocr_test,
        )
        from app.devtools.sandbox import (
            cleanup_sandbox,
            create_sandbox_copy,
            resolve_core_db_path,
        )
        from app.devtools.tesseract_probe import probe_tesseract

        tenant = str(args.tenant or "").strip() or "default"
        timeout_s = max(1, int(args.timeout))
        preferred_langs = (
            [str(args.lang).strip()] if str(args.lang or "").strip() else None
        )
        base_db = resolve_core_db_path()
        base_status = get_policy_status(tenant, db_path=base_db)

        if args.show_tesseract:
            from app.autonomy.ocr import resolve_tesseract_bin

            resolved = resolve_tesseract_bin()
            probe = probe_tesseract(
                bin_path=str(resolved) if resolved else None,
                tessdata_dir=str(args.tessdata_dir or "").strip() or None,
                preferred_langs=preferred_langs,
            )
            result = _policy_view_payload(
                tenant=tenant,
                status=base_status,
                next_actions=list(probe.get("next_actions") or []),
            )
            result["ok"] = bool(probe.get("ok"))
            result["reason"] = str(probe.get("reason") or "") or None
            result["message"] = _reason_message(result["reason"])
            result["tesseract_found"] = bool(probe.get("bin_path"))
            result["tessdata_dir"] = _sanitize_path(
                str(probe.get("tessdata_dir") or "") or None
            )
            result["tessdata_source"] = str(probe.get("tessdata_source") or "") or None
            result["tesseract_langs"] = [
                str(item) for item in list(probe.get("langs") or [])
            ]
            result["tesseract_lang_used"] = str(probe.get("lang_used") or "") or None
            result["tesseract_probe_reason"] = str(probe.get("reason") or "") or None
            result["tesseract_probe_next_actions"] = list(
                probe.get("next_actions") or []
            )
            result["tesseract_stderr_tail"] = (
                str(probe.get("stderr_tail") or "") or None
            )
            if not result["next_actions"]:
                result["next_actions"] = list(probe.get("next_actions") or [])
        elif args.show_policy:
            result = _policy_view_payload(
                tenant=tenant,
                status=base_status,
                next_actions=next_actions_for_reason(_status_reason(base_status)),
            )
        elif args.no_sandbox:
            if args.enable_policy_in_sandbox:
                result = _policy_view_payload(
                    tenant=tenant,
                    status=base_status,
                    next_actions=next_actions_for_reason("invalid_args"),
                )
                result["ok"] = False
                result["reason"] = "invalid_args"
                result["policy_reason"] = "invalid_args"
                result["message"] = _reason_message("invalid_args")
            else:
                result = run_ocr_test(
                    tenant,
                    timeout_s=timeout_s,
                    sandbox=False,
                    keep_artifacts=bool(args.keep_artifacts),
                    seed_watch_config_in_sandbox=False,
                    direct_submit_in_sandbox=False,
                    tessdata_dir=str(args.tessdata_dir or "").strip() or None,
                    lang=(preferred_langs[0] if preferred_langs else None),
                )
                _merge_policy_fields(
                    result,
                    base_status=base_status,
                    effective_status=base_status,
                )
        else:
            sandbox_db, sandbox_dir = create_sandbox_copy(tenant)
            try:
                effective_status = get_policy_status(tenant, db_path=sandbox_db)
                enable_status: dict[str, Any] | None = None
                if args.enable_policy_in_sandbox:
                    enable_status = enable_ocr_policy_in_db(
                        tenant,
                        db_path=sandbox_db,
                        confirm=True,
                        read_only=detect_read_only(),
                    )
                    effective_status = get_policy_status(tenant, db_path=sandbox_db)

                result = run_ocr_test(
                    tenant,
                    timeout_s=timeout_s,
                    sandbox=False,
                    keep_artifacts=bool(args.keep_artifacts),
                    db_path_override=Path(str(sandbox_db)),
                    seed_watch_config_in_sandbox=bool(
                        args.seed_watch_config_in_sandbox
                    ),
                    direct_submit_in_sandbox=bool(args.direct_submit_in_sandbox),
                    tessdata_dir=str(args.tessdata_dir or "").strip() or None,
                    lang=(preferred_langs[0] if preferred_langs else None),
                )
                result["sandbox"] = True
                result["sandbox_db_path"] = (
                    str(sandbox_db) if bool(args.keep_artifacts) else None
                )
                _merge_policy_fields(
                    result,
                    base_status=base_status,
                    effective_status=effective_status,
                )
                if enable_status and not bool(enable_status.get("ok")):
                    reason = str(enable_status.get("reason") or "policy_denied")
                    result["ok"] = False
                    result["reason"] = reason
                    result["policy_reason"] = reason
                    if result.get("existing_columns") is None:
                        result["existing_columns"] = _status_columns(effective_status)
                    result["next_actions"] = next_actions_for_reason(reason)
                    result["message"] = _reason_message(reason)
            finally:
                if not bool(args.keep_artifacts):
                    cleanup_sandbox(sandbox_dir)
    except Exception as exc:
        payload = {
            "ok": False,
            "reason": "unexpected_error",
            "message": type(exc).__name__,
        }
        print(json.dumps(payload, sort_keys=True))
        return 3

    result["sandbox_db_path"] = _sanitize_path(
        str(result.get("sandbox_db_path") or "") or None
    )
    result["inbox_dir_used"] = _sanitize_path(
        str(result.get("inbox_dir_used") or "") or None
    )
    result["tessdata_dir"] = _sanitize_path(
        str(result.get("tessdata_dir") or "") or None
    )

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(_human_report(result))
    return 0 if bool(result.get("ok")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
