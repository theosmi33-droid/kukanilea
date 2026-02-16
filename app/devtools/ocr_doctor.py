from __future__ import annotations

import json
import platform
import re
from pathlib import Path
from typing import Any

from app.devtools.ocr_policy import enable_ocr_policy_in_db, get_policy_status
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

TEST_MARKERS = (
    "pilot+test@example.com",
    "+49 151 12345678",
    "OCR_Test_2026-02-16_KD-9999",
)
POSIX_ABS_RE = re.compile(r"(?<![A-Za-z0-9>])/[^\s\"']+")
WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")
WINDOWS_UNC_RE = re.compile(r"\\\\[A-Za-z0-9_.-]+\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")


def _resolve_config_object() -> Any:
    import app.config as config_module

    for name in ("Config", "Settings", "AppConfig"):
        candidate = getattr(config_module, name, None)
        if candidate is not None and hasattr(candidate, "CORE_DB"):
            return candidate
    if hasattr(config_module, "CORE_DB"):
        return config_module
    return None


def _sanitize_string(raw: str) -> str:
    text = str(raw or "").replace("\x00", "").replace("\r", "").strip()
    for marker in TEST_MARKERS:
        text = text.replace(marker, "<redacted>")
    text = WINDOWS_UNC_RE.sub("<path>", text)
    text = WINDOWS_DRIVE_RE.sub("<path>", text)
    text = POSIX_ABS_RE.sub("<path>", text)
    lines = [line for line in text.splitlines() if line]
    if len(lines) > 20:
        lines = lines[-20:]
    out = "\n".join(lines)
    if len(out) > 2000:
        out = out[-2000:]
    return out


def _sanitize_path_for_env(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    p = Path(text)
    home = str(Path.home())
    if text.startswith(home):
        return f"<HOME>/{p.name}"
    if p.is_absolute():
        return f"<path>/{p.name}"
    return _sanitize_string(text)


def _sanitize_for_report(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_for_report(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_report(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_for_report(v) for v in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


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


def _capture_environment() -> dict[str, Any]:
    cfg = _resolve_config_object()
    app_version = None
    try:
        import importlib.metadata as importlib_metadata

        app_version = importlib_metadata.version("kukanilea")
    except Exception:
        app_version = None
    config_paths = {
        "core_db": _sanitize_path_for_env(getattr(cfg, "CORE_DB", None))
        if cfg is not None
        else None,
        "auth_db": _sanitize_path_for_env(getattr(cfg, "AUTH_DB", None))
        if cfg is not None
        else None,
        "license_path": _sanitize_path_for_env(getattr(cfg, "LICENSE_PATH", None))
        if cfg is not None
        else None,
        "trial_path": _sanitize_path_for_env(getattr(cfg, "TRIAL_PATH", None))
        if cfg is not None
        else None,
    }
    return {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "app_version": app_version,
        "config_paths": config_paths,
    }


def _exit_code_for_result(result: dict[str, Any], *, strict: bool) -> int:
    ok = bool(result.get("ok"))
    reason = str(result.get("reason") or "")
    if ok:
        if reason == "ok_with_warnings":
            return 1 if strict else 2
        return 0
    return 1


def _doctor_message(reason: str | None, *, ok: bool) -> str:
    key = str(reason or "")
    if ok and key == "ok_with_warnings":
        return "OCR doctor completed with warnings."
    if ok:
        return "OCR doctor completed successfully."
    if key == "commit_guard_failed":
        return "Real policy commit refused by guard. Use exact tenant echo to confirm."
    if key == "read_only":
        return "READ_ONLY active; mutation path refused."
    if key:
        return f"OCR doctor failed: {key}"
    return "OCR doctor failed."


def _doctor_next_actions(reason: str | None, probe_actions: list[str]) -> list[str]:
    key = str(reason or "")
    if key == "commit_guard_failed":
        return [
            "Re-run with --yes-really-commit set to the exact tenant id.",
            "Prefer sandbox mode unless a real-DB update is explicitly required.",
        ]
    if key == "ok_with_warnings":
        return [
            "Review tesseract warnings and verify tessdata/language packs.",
            "Use --strict for CI runs that must fail on warnings.",
        ]
    mapped = next_actions_for_reason(key)
    if mapped:
        return mapped
    return [str(item) for item in list(probe_actions or [])]


def format_doctor_report(report: dict[str, Any]) -> str:
    lines = [
        "OCR Doctor Report",
        f"tenant: {report.get('tenant_id')}",
        f"ok: {bool(report.get('ok'))}",
        f"reason: {report.get('reason') or '-'}",
        f"strict_mode: {bool(report.get('strict_mode'))}",
        f"sandbox: {bool(report.get('sandbox'))}",
        f"read_only: {bool(report.get('read_only'))}",
        f"policy_enabled_base: {report.get('policy_enabled_base')}",
        f"policy_enabled_effective: {report.get('policy_enabled_effective')}",
        f"policy_reason: {report.get('policy_reason') or '-'}",
        f"tesseract_probe_reason: {report.get('probe_reason') or '-'}",
        f"tesseract_version: {report.get('tesseract_version') or '-'}",
        f"lang_used: {report.get('lang_used') or '-'}",
        f"job_status: {report.get('job_status') or '-'}",
        f"job_error_code: {report.get('job_error_code') or '-'}",
        f"scanner_discovered_files: {report.get('scanner_discovered_files')}",
        f"watch_config_seeded: {bool(report.get('watch_config_seeded'))}",
        f"direct_submit_used: {bool(report.get('direct_submit_used'))}",
        f"pii_found_knowledge: {bool(report.get('pii_found_knowledge'))}",
        f"pii_found_eventlog: {bool(report.get('pii_found_eventlog'))}",
        f"commit_real_policy_requested: {bool(report.get('commit_real_policy_requested'))}",
        f"commit_real_policy_applied: {bool(report.get('commit_real_policy_applied'))}",
        f"commit_real_policy_reason: {report.get('commit_real_policy_reason') or '-'}",
        f"next_actions: {report.get('next_actions') or '-'}",
        f"message: {report.get('message') or '-'}",
    ]
    return "\n".join(lines)


def _smoke_result_with_policy_merge(
    *,
    tenant_id: str,
    timeout_s: int,
    strict: bool,
    no_retry: bool,
    tesseract_bin: str | None,
    tessdata_dir: str | None,
    lang: str | None,
    sandbox: bool,
    enable_policy_in_sandbox: bool,
    seed_watch_config_in_sandbox: bool,
    direct_submit_in_sandbox: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    base_db = resolve_core_db_path()
    base_status = get_policy_status(tenant_id, db_path=base_db)
    if not sandbox:
        smoke = run_ocr_test(
            tenant_id,
            timeout_s=timeout_s,
            sandbox=False,
            keep_artifacts=False,
            seed_watch_config_in_sandbox=False,
            direct_submit_in_sandbox=False,
            tessdata_dir=tessdata_dir,
            tesseract_bin=tesseract_bin,
            lang=lang,
            strict=strict,
            retry_enabled=not bool(no_retry),
        )
        _merge_policy_fields(
            smoke, base_status=base_status, effective_status=base_status
        )
        return smoke, base_status, base_status, None

    sandbox_db, sandbox_dir = create_sandbox_copy(tenant_id)
    enable_status: dict[str, Any] | None = None
    try:
        effective_status = get_policy_status(tenant_id, db_path=sandbox_db)
        if enable_policy_in_sandbox:
            enable_status = enable_ocr_policy_in_db(
                tenant_id,
                db_path=sandbox_db,
                confirm=True,
                read_only=detect_read_only(),
            )
            effective_status = get_policy_status(tenant_id, db_path=sandbox_db)
        smoke = run_ocr_test(
            tenant_id,
            timeout_s=timeout_s,
            sandbox=False,
            keep_artifacts=False,
            db_path_override=Path(str(sandbox_db)),
            seed_watch_config_in_sandbox=bool(seed_watch_config_in_sandbox),
            direct_submit_in_sandbox=bool(direct_submit_in_sandbox),
            tessdata_dir=tessdata_dir,
            tesseract_bin=tesseract_bin,
            lang=lang,
            strict=strict,
            retry_enabled=not bool(no_retry),
        )
        smoke["sandbox"] = True
        smoke["sandbox_db_path"] = str(sandbox_db)
        _merge_policy_fields(
            smoke, base_status=base_status, effective_status=effective_status
        )
        if enable_status and not bool(enable_status.get("ok")):
            reason = str(enable_status.get("reason") or "policy_denied")
            smoke["ok"] = False
            smoke["reason"] = reason
            smoke["policy_reason"] = reason
            if smoke.get("existing_columns") is None:
                smoke["existing_columns"] = _status_columns(effective_status)
            smoke["next_actions"] = next_actions_for_reason(reason)
        return smoke, base_status, effective_status, enable_status
    finally:
        cleanup_sandbox(sandbox_dir)


def run_ocr_doctor(
    tenant_id: str,
    *,
    json_mode: bool,
    strict: bool,
    timeout_s: int,
    sandbox: bool = True,
    enable_policy_in_sandbox: bool = True,
    seed_watch_config_in_sandbox: bool = True,
    direct_submit_in_sandbox: bool = True,
    no_retry: bool = False,
    tesseract_bin: str | None = None,
    tessdata_dir: str | None = None,
    lang: str | None = None,
    commit_real_policy: bool = False,
    yes_really_commit: str | None = None,
) -> tuple[dict[str, Any], int]:
    tenant = str(tenant_id or "").strip() or "default"
    read_only = detect_read_only()
    env_info = _capture_environment()

    base_db = resolve_core_db_path()

    probe = probe_tesseract(
        bin_path=str(tesseract_bin or "").strip() or None,
        tessdata_dir=tessdata_dir,
        preferred_langs=[lang] if str(lang or "").strip() else None,
    )

    commit_applied = False
    commit_reason: str | None = None
    if commit_real_policy:
        if str(yes_really_commit or "") != tenant:
            commit_reason = "commit_guard_failed"
        elif read_only:
            commit_reason = "read_only"
        else:
            commit_status = enable_ocr_policy_in_db(
                tenant,
                db_path=base_db,
                confirm=True,
                read_only=False,
            )
            if bool(commit_status.get("ok")):
                commit_applied = True
            else:
                commit_reason = str(commit_status.get("reason") or "policy_denied")

    smoke, base_status_after, effective_status, _enable_status = (
        _smoke_result_with_policy_merge(
            tenant_id=tenant,
            timeout_s=max(1, int(timeout_s)),
            strict=bool(strict),
            no_retry=bool(no_retry),
            tesseract_bin=tesseract_bin,
            tessdata_dir=tessdata_dir,
            lang=lang,
            sandbox=bool(sandbox),
            enable_policy_in_sandbox=bool(enable_policy_in_sandbox),
            seed_watch_config_in_sandbox=bool(seed_watch_config_in_sandbox),
            direct_submit_in_sandbox=bool(direct_submit_in_sandbox),
        )
    )

    reason: str | None = None
    ok = bool(smoke.get("ok"))
    probe_reason = str(probe.get("reason") or "") or None

    if commit_reason:
        ok = False
        reason = commit_reason
    elif not ok:
        reason = str(smoke.get("reason") or "failed")
    elif probe_reason == "ok_with_warnings":
        reason = "ok_with_warnings"
        ok = True

    if bool(strict) and reason == "ok_with_warnings":
        ok = False
        reason = "tesseract_warning"

    next_actions = _doctor_next_actions(
        reason, [str(item) for item in list(probe.get("next_actions") or [])]
    )
    message = _doctor_message(reason, ok=ok)

    report: dict[str, Any] = {
        "ok": ok,
        "reason": reason,
        "message": message,
        "tenant_id": tenant,
        "json_mode": bool(json_mode),
        "strict_mode": bool(strict),
        "sandbox": bool(sandbox),
        "read_only": bool(read_only),
        "timeout_s": max(1, int(timeout_s)),
        "retry_enabled": not bool(no_retry),
        "environment": env_info,
        "policy_enabled_base": _status_enabled(base_status_after),
        "policy_enabled_effective": _status_enabled(effective_status),
        "policy_reason": _status_reason(effective_status),
        "existing_columns": _status_columns(effective_status),
        "probe_reason": probe_reason,
        "probe_next_actions": [
            str(item) for item in list(probe.get("next_actions") or [])
        ],
        "tesseract_found": bool(probe.get("tesseract_found") or probe.get("bin_path")),
        "tesseract_bin_used": str(
            probe.get("tesseract_bin_used") or probe.get("bin_path") or ""
        ),
        "tesseract_version": str(probe.get("tesseract_version") or "") or None,
        "supports_print_tessdata_dir": bool(probe.get("supports_print_tessdata_dir")),
        "print_tessdata_dir": str(probe.get("print_tessdata_dir") or "") or None,
        "tessdata_candidates": [
            str(item) for item in list(probe.get("tessdata_candidates") or [])
        ],
        "tessdata_prefix_used": str(
            probe.get("tessdata_prefix")
            or probe.get("tessdata_dir_used")
            or probe.get("tessdata_dir")
            or ""
        )
        or None,
        "lang_used": str(probe.get("lang_selected") or probe.get("lang_used") or "")
        or None,
        "tesseract_langs": [str(item) for item in list(probe.get("langs") or [])],
        "tesseract_warnings": [str(item) for item in list(probe.get("warnings") or [])],
        "tesseract_stderr_tail": str(probe.get("stderr_tail") or "") or None,
        "commit_real_policy_requested": bool(commit_real_policy),
        "commit_real_policy_applied": bool(commit_applied),
        "commit_real_policy_reason": commit_reason,
        "smoke": smoke,
        "job_status": smoke.get("job_status"),
        "job_error_code": smoke.get("job_error_code"),
        "scanner_discovered_files": int(smoke.get("scanner_discovered_files") or 0),
        "watch_config_seeded": bool(smoke.get("watch_config_seeded")),
        "watch_config_existed": smoke.get("watch_config_existed"),
        "inbox_dir_used": smoke.get("inbox_dir_used"),
        "direct_submit_used": bool(smoke.get("direct_submit_used")),
        "pii_found_knowledge": bool(smoke.get("pii_found_knowledge")),
        "pii_found_eventlog": bool(smoke.get("pii_found_eventlog")),
        "next_actions": next_actions,
    }

    report = _sanitize_for_report(report)
    report["smoke"] = _sanitize_for_report(report.get("smoke") or {})

    exit_code = _exit_code_for_result(report, strict=bool(strict))
    return report, exit_code


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True)
