from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _reason_message(reason: str | None) -> str:
    key = str(reason or "")
    if not key:
        return "OK"
    if key == "policy_denied":
        return "OCR policy is disabled for tenant."
    if key == "tesseract_missing":
        return "Tesseract binary not found."
    if key == "tesseract_not_allowlisted":
        return "Tesseract binary is present but not allowlisted."
    if key == "tesseract_exec_failed":
        return "Tesseract binary resolved, but execution failed."
    if key == "tessdata_missing":
        return "Tesseract data files were not found."
    if key == "language_missing":
        return "Requested OCR language is unavailable."
    if key == "tesseract_failed":
        return "Tesseract execution failed."
    if key == "config_file_missing":
        return "Tesseract config file could not be loaded."
    if key == "tesseract_warning":
        return "Tesseract reported warnings and strict mode rejected the run."
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
    if key == "input_too_small":
        return "Embedded OCR smoke image is unexpectedly small."
    if key == "test_image_invalid":
        return "Embedded OCR smoke image is invalid."
    if key == "job_not_found":
        return "No OCR job was detected within timeout."
    if key == "invalid_args":
        return "Invalid CLI argument combination."
    if key == "commit_guard_failed":
        return "Real policy commit refused by guard."
    if key == "support_bundle_failed":
        return "Support bundle creation failed."
    return "OCR test failed."


def _sanitize_path(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if (
        text.startswith("/")
        or re.match(r"^[A-Za-z]:\\", text)
        or text.startswith("\\\\")
    ):
        return "<path>"
    return text


def _valid_tesseract_bin(path_value: str | None) -> bool:
    if not str(path_value or "").strip():
        return True
    p = Path(str(path_value)).expanduser()
    return p.exists() and p.is_file() and os.access(p, os.R_OK | os.X_OK)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as fh:
        fh.write(content)
        tmp_name = fh.name
    os.replace(tmp_name, path)


def _write_proof_bundle(
    *,
    report: dict[str, Any],
    proof_dir: Path,
) -> None:
    doctor_path = proof_dir / "ocr_doctor_proof.json"
    smoke_path = proof_dir / "ocr_sandbox_e2e_proof.json"
    _atomic_write_text(doctor_path, json.dumps(report, sort_keys=True) + "\n")
    _atomic_write_text(
        smoke_path, json.dumps(report.get("smoke") or {}, sort_keys=True) + "\n"
    )


def _default_bundle_dir(tenant: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_tenant = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(tenant or "default"))[:64]
    return Path("docs/devtools/support_bundles") / f"{stamp}-{safe_tenant}"


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
        "tesseract_allowlisted": False,
        "tesseract_allowlist_reason": None,
        "tesseract_allowed_prefixes": [],
        "tesseract_bin_used_probe": None,
        "tesseract_resolution_source_probe": None,
        "tesseract_bin_used_job": None,
        "tesseract_resolution_source_job": None,
        "tesseract_allowlisted_job": None,
        "tesseract_allowlist_reason_job": None,
        "tesseract_exec_errno": None,
        "tesseract_version": None,
        "supports_print_tessdata_dir": False,
        "tessdata_dir": None,
        "tessdata_source": None,
        "tessdata_candidates": [],
        "print_tessdata_dir": None,
        "tesseract_bin_used": None,
        "tesseract_langs": [],
        "tesseract_lang_used": None,
        "tesseract_warnings": [],
        "tesseract_probe_reason": None,
        "tesseract_probe_next_actions": [],
        "tesseract_stderr_tail": None,
        "tessdata_prefix_used": None,
        "lang_used": None,
        "probe_reason": None,
        "probe_next_actions": [],
        "stderr_tail": None,
        "strict_mode": False,
        "retry_enabled": True,
        "tesseract_retry_used": False,
        "lang_fallback_used": False,
        "tessdata_fallback_used": False,
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
        f"tesseract_allowlisted: {bool(result.get('tesseract_allowlisted'))}",
        f"tesseract_allowlist_reason: {result.get('tesseract_allowlist_reason') or '-'}",
        f"tesseract_allowed_prefixes: {result.get('tesseract_allowed_prefixes') or '-'}",
        f"tesseract_bin_used_probe: {result.get('tesseract_bin_used_probe') or '-'}",
        f"tesseract_resolution_source_probe: {result.get('tesseract_resolution_source_probe') or '-'}",
        f"tesseract_bin_used_job: {result.get('tesseract_bin_used_job') or '-'}",
        f"tesseract_resolution_source_job: {result.get('tesseract_resolution_source_job') or '-'}",
        f"tesseract_allowlisted_job: {result.get('tesseract_allowlisted_job')}",
        f"tesseract_allowlist_reason_job: {result.get('tesseract_allowlist_reason_job') or '-'}",
        f"tesseract_exec_errno: {result.get('tesseract_exec_errno') if result.get('tesseract_exec_errno') is not None else '-'}",
        f"tesseract_version: {result.get('tesseract_version') or '-'}",
        f"supports_print_tessdata_dir: {bool(result.get('supports_print_tessdata_dir'))}",
        f"tessdata_dir: {result.get('tessdata_dir') or '-'}",
        f"tessdata_source: {result.get('tessdata_source') or '-'}",
        f"tessdata_candidates: {result.get('tessdata_candidates') or '-'}",
        f"print_tessdata_dir: {result.get('print_tessdata_dir') or '-'}",
        f"tesseract_bin_used: {result.get('tesseract_bin_used') or '-'}",
        f"tesseract_langs: {result.get('tesseract_langs') or '-'}",
        f"tesseract_lang_used: {result.get('tesseract_lang_used') or '-'}",
        f"tesseract_warnings: {result.get('tesseract_warnings') or '-'}",
        f"tesseract_probe_reason: {result.get('tesseract_probe_reason') or '-'}",
        f"tesseract_stderr_tail: {result.get('tesseract_stderr_tail') or '-'}",
        f"tessdata_prefix_used: {result.get('tessdata_prefix_used') or '-'}",
        f"lang_used: {result.get('lang_used') or '-'}",
        f"probe_reason: {result.get('probe_reason') or '-'}",
        f"stderr_tail: {result.get('stderr_tail') or '-'}",
        f"strict_mode: {bool(result.get('strict_mode'))}",
        f"retry_enabled: {bool(result.get('retry_enabled'))}",
        f"tesseract_retry_used: {bool(result.get('tesseract_retry_used'))}",
        f"lang_fallback_used: {bool(result.get('lang_fallback_used'))}",
        f"tessdata_fallback_used: {bool(result.get('tessdata_fallback_used'))}",
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


def _exit_code_for_result(result: dict[str, Any], *, strict: bool) -> int:
    ok = bool(result.get("ok"))
    reason = str(result.get("reason") or "")
    if ok:
        if reason == "ok_with_warnings":
            return 1 if strict else 2
        return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OCR pipeline verification test")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--show-policy", action="store_true")
    parser.add_argument("--show-tesseract", action="store_true")
    parser.add_argument("--enable-policy-in-sandbox", action="store_true")
    parser.add_argument("--no-sandbox", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--exit-nonzero-on-warnings",
        dest="strict",
        action="store_true",
    )
    parser.add_argument("--no-retry", action="store_true")
    parser.add_argument("--tesseract-bin")
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
    parser.add_argument("--commit-real-policy", action="store_true")
    parser.add_argument("--yes-really-commit")
    parser.add_argument("--write-proof", action="store_true")
    parser.add_argument("--proof-dir", default="docs/devtools")
    parser.add_argument("--report-json-path")
    parser.add_argument("--report-text-path")
    parser.add_argument("--write-support-bundle", action="store_true")
    parser.add_argument("--bundle-dir")
    parser.add_argument("--zip-bundle", dest="zip_bundle", action="store_true")
    parser.add_argument("--no-zip-bundle", dest="zip_bundle", action="store_false")
    parser.add_argument("--doctor-only", action="store_true")
    parser.add_argument("--doctor-and-sandbox", action="store_true")
    parser.set_defaults(zip_bundle=True)
    args = parser.parse_args()

    try:
        # Lazy import keeps sandbox env wiring possible before heavy modules.
        from app.devtools.ocr_doctor import (
            format_doctor_report,
            report_to_json,
            run_ocr_doctor,
        )
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
        from app.devtools.support_bundle import write_support_bundle
        from app.devtools.tesseract_probe import probe_tesseract

        tenant = str(args.tenant or "").strip() or "default"
        timeout_s = max(1, int(args.timeout))
        tesseract_bin_override = str(args.tesseract_bin or "").strip() or None
        preferred_langs = (
            [str(args.lang).strip()] if str(args.lang or "").strip() else None
        )
        base_db = resolve_core_db_path()
        base_status = get_policy_status(tenant, db_path=base_db)

        if bool(args.write_support_bundle) and not bool(args.doctor):
            args.doctor = True

        if args.doctor and (args.show_policy or args.show_tesseract):
            result = _policy_view_payload(
                tenant=tenant,
                status=base_status,
                next_actions=next_actions_for_reason("invalid_args"),
            )
            result["ok"] = False
            result["reason"] = "invalid_args"
            result["policy_reason"] = "invalid_args"
            result["message"] = _reason_message("invalid_args")
            if args.json:
                print(json.dumps(result, sort_keys=True))
            else:
                print(_human_report(result))
            return 1

        if args.doctor:
            if bool(args.doctor_only) and bool(args.doctor_and_sandbox):
                result = _policy_view_payload(
                    tenant=tenant,
                    status=base_status,
                    next_actions=next_actions_for_reason("invalid_args"),
                )
                result["ok"] = False
                result["reason"] = "invalid_args"
                result["policy_reason"] = "invalid_args"
                result["message"] = _reason_message("invalid_args")
                if args.json:
                    print(json.dumps(result, sort_keys=True))
                else:
                    print(_human_report(result))
                return 1

            if bool(args.doctor_only):
                run_sandbox_e2e = False
            elif bool(args.doctor_and_sandbox) or bool(args.write_support_bundle):
                run_sandbox_e2e = True
            else:
                run_sandbox_e2e = not bool(args.no_sandbox)

            if bool(args.no_sandbox) and run_sandbox_e2e:
                result = _policy_view_payload(
                    tenant=tenant,
                    status=base_status,
                    next_actions=next_actions_for_reason("invalid_args"),
                )
                result["ok"] = False
                result["reason"] = "invalid_args"
                result["policy_reason"] = "invalid_args"
                result["message"] = _reason_message("invalid_args")
                if args.json:
                    print(json.dumps(result, sort_keys=True))
                else:
                    print(_human_report(result))
                return 1

            report, doctor_exit = run_ocr_doctor(
                tenant,
                json_mode=bool(args.json),
                strict=bool(args.strict),
                timeout_s=timeout_s,
                sandbox=not bool(args.no_sandbox),
                enable_policy_in_sandbox=(
                    bool(args.enable_policy_in_sandbox) or not bool(args.no_sandbox)
                ),
                seed_watch_config_in_sandbox=bool(args.seed_watch_config_in_sandbox),
                direct_submit_in_sandbox=(
                    bool(args.direct_submit_in_sandbox) or not bool(args.no_sandbox)
                ),
                no_retry=bool(args.no_retry),
                tesseract_bin=tesseract_bin_override,
                tessdata_dir=str(args.tessdata_dir or "").strip() or None,
                lang=(preferred_langs[0] if preferred_langs else None),
                commit_real_policy=bool(args.commit_real_policy),
                yes_really_commit=str(args.yes_really_commit or "").strip() or None,
                run_sandbox_e2e=bool(run_sandbox_e2e),
            )
            if str(args.report_json_path or "").strip():
                _atomic_write_text(
                    Path(str(args.report_json_path)),
                    report_to_json(report) + "\n",
                )
            if str(args.report_text_path or "").strip():
                _atomic_write_text(
                    Path(str(args.report_text_path)),
                    format_doctor_report(report) + "\n",
                )
            if bool(args.write_proof):
                _write_proof_bundle(
                    report=report,
                    proof_dir=Path(str(args.proof_dir or "docs/devtools")),
                )
            if bool(args.write_support_bundle):
                bundle_dir = (
                    Path(str(args.bundle_dir))
                    if str(args.bundle_dir or "").strip()
                    else _default_bundle_dir(tenant)
                )
                bundle = write_support_bundle(
                    tenant,
                    bundle_dir,
                    doctor_result=report,
                    sandbox_e2e_result=report.get("smoke") if run_sandbox_e2e else None,
                    extra={
                        "strict_mode": bool(args.strict),
                        "doctor_mode": True,
                        "run_sandbox_e2e": bool(run_sandbox_e2e),
                    },
                    atomic=True,
                    zip_bundle=bool(args.zip_bundle),
                )
                report["support_bundle"] = bundle
                if not bool(bundle.get("ok")):
                    report["ok"] = False
                    report["reason"] = "support_bundle_failed"
                    report["message"] = _reason_message("support_bundle_failed")
                    report["next_actions"] = list(
                        dict.fromkeys(
                            [
                                *list(report.get("next_actions") or []),
                                "Re-run with --write-support-bundle and verify output directory permissions.",
                            ]
                        )
                    )
                    doctor_exit = 1
            if args.json:
                print(report_to_json(report))
            else:
                print(format_doctor_report(report))
                if report.get("support_bundle"):
                    bundle = dict(report.get("support_bundle") or {})
                    print(f"support_bundle_ok: {bool(bundle.get('ok'))}")
                    print(f"support_bundle_dir: {bundle.get('bundle_dir') or '-'}")
                    print(f"support_bundle_zip: {bundle.get('zip_path') or '-'}")
            return int(doctor_exit)

        if not _valid_tesseract_bin(tesseract_bin_override):
            result = _policy_view_payload(
                tenant=tenant,
                status=base_status,
                next_actions=next_actions_for_reason("tesseract_missing"),
            )
            result["ok"] = False
            result["reason"] = "tesseract_missing"
            result["message"] = _reason_message("tesseract_missing")
            result["tesseract_bin_used"] = _sanitize_path(tesseract_bin_override)
            if args.json:
                print(json.dumps(result, sort_keys=True))
            else:
                print(_human_report(result))
            return 1

        if args.show_tesseract:
            from app.autonomy.ocr import resolve_tesseract_bin

            resolved = resolve_tesseract_bin()
            probe = probe_tesseract(
                bin_path=tesseract_bin_override
                or (str(resolved) if resolved else None),
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
            result["tesseract_found"] = bool(
                probe.get("tesseract_found") or probe.get("bin_path")
            )
            result["tesseract_allowlisted"] = bool(probe.get("tesseract_allowlisted"))
            result["tesseract_allowlist_reason"] = (
                str(probe.get("tesseract_allowlist_reason") or "") or None
            )
            result["tesseract_allowed_prefixes"] = [
                _sanitize_path(str(item))
                for item in list(probe.get("tesseract_allowed_prefixes") or [])
            ]
            result["tesseract_bin_used_probe"] = _sanitize_path(
                str(probe.get("tesseract_bin_used") or probe.get("bin_path") or "")
                or None
            )
            result["tesseract_resolution_source_probe"] = (
                str(probe.get("resolution_source") or "") or None
            )
            result["tessdata_dir"] = _sanitize_path(
                str(
                    probe.get("tessdata_prefix")
                    or probe.get("tessdata_dir_used")
                    or probe.get("tessdata_dir")
                    or ""
                )
                or None
            )
            result["tessdata_source"] = str(probe.get("tessdata_source") or "") or None
            result["tesseract_version"] = (
                str(probe.get("tesseract_version") or "") or None
            )
            result["supports_print_tessdata_dir"] = bool(
                probe.get("supports_print_tessdata_dir")
            )
            result["tessdata_candidates"] = [
                _sanitize_path(str(item))
                for item in list(probe.get("tessdata_candidates") or [])
            ]
            result["print_tessdata_dir"] = _sanitize_path(
                str(probe.get("print_tessdata_dir") or "") or None
            )
            result["tesseract_bin_used"] = _sanitize_path(
                str(probe.get("tesseract_bin_used") or probe.get("bin_path") or "")
                or None
            )
            result["tesseract_langs"] = [
                str(item) for item in list(probe.get("langs") or [])
            ]
            result["tesseract_lang_used"] = (
                str(probe.get("lang_selected") or probe.get("lang_used") or "") or None
            )
            result["tesseract_warnings"] = [
                str(item) for item in list(probe.get("warnings") or [])
            ]
            result["tesseract_probe_reason"] = str(probe.get("reason") or "") or None
            result["tesseract_probe_next_actions"] = list(
                probe.get("next_actions") or []
            )
            result["tesseract_stderr_tail"] = (
                str(probe.get("stderr_tail") or "") or None
            )
            result["tessdata_prefix_used"] = result["tessdata_dir"]
            result["lang_used"] = result["tesseract_lang_used"]
            result["probe_reason"] = result["tesseract_probe_reason"]
            result["probe_next_actions"] = list(result["tesseract_probe_next_actions"])
            result["stderr_tail"] = result["tesseract_stderr_tail"]
            result["strict_mode"] = bool(args.strict)
            result["retry_enabled"] = not bool(args.no_retry)
            if bool(args.strict) and result["reason"] == "ok_with_warnings":
                result["ok"] = False
                result["reason"] = "tesseract_warning"
                result["message"] = _reason_message(result["reason"])
                result["next_actions"] = [
                    "Warnings were treated as fatal because --strict is enabled."
                ]
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
                    tesseract_bin=tesseract_bin_override,
                    lang=(preferred_langs[0] if preferred_langs else None),
                    strict=bool(args.strict),
                    retry_enabled=not bool(args.no_retry),
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
                    tesseract_bin=tesseract_bin_override,
                    lang=(preferred_langs[0] if preferred_langs else None),
                    strict=bool(args.strict),
                    retry_enabled=not bool(args.no_retry),
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
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print("OCR Devtools Test")
            print("ok: False")
            print("reason: unexpected_error")
            print(f"message: {type(exc).__name__}")
        return 1

    result["sandbox_db_path"] = _sanitize_path(
        str(result.get("sandbox_db_path") or "") or None
    )
    result["inbox_dir_used"] = _sanitize_path(
        str(result.get("inbox_dir_used") or "") or None
    )
    result["tessdata_dir"] = _sanitize_path(
        str(result.get("tessdata_dir") or "") or None
    )
    result["print_tessdata_dir"] = _sanitize_path(
        str(result.get("print_tessdata_dir") or "") or None
    )
    result["tesseract_bin_used"] = _sanitize_path(
        str(result.get("tesseract_bin_used") or "") or None
    )
    result["tessdata_candidates"] = [
        _sanitize_path(str(item))
        for item in list(result.get("tessdata_candidates") or [])
    ]
    result["tesseract_allowed_prefixes"] = [
        _sanitize_path(str(item))
        for item in list(result.get("tesseract_allowed_prefixes") or [])
    ]
    result["tesseract_bin_used_probe"] = _sanitize_path(
        str(result.get("tesseract_bin_used_probe") or "") or None
    )
    result["tesseract_bin_used_job"] = _sanitize_path(
        str(result.get("tesseract_bin_used_job") or "") or None
    )
    result["tessdata_prefix_used"] = result.get("tessdata_dir")
    result["lang_used"] = result.get("tesseract_lang_used")
    result["probe_reason"] = result.get("tesseract_probe_reason")
    result["probe_next_actions"] = list(
        result.get("tesseract_probe_next_actions") or []
    )
    result["stderr_tail"] = result.get("tesseract_stderr_tail")

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(_human_report(result))
    return _exit_code_for_result(result, strict=bool(args.strict))


if __name__ == "__main__":
    raise SystemExit(main())
