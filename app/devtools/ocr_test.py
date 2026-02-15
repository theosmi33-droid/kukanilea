from __future__ import annotations

import base64
import contextlib
import os
import shutil
import sqlite3
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

import kukanilea_core_v3_fixed as legacy_core

TEST_EMAIL_PATTERN = "pilot+test@example.com"
TEST_PHONE_PATTERN = "+49 151 12345678"
TEST_IMAGE_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y8Y3f8AAAAASUVORK5CYII="
ENV_DB_KEYS = (
    "KUKANILEA_CORE_DB",
    "KUKANILEA_AUTH_DB",
    "DB_FILENAME",
    "TOPHANDWERK_DB_FILENAME",
    "KUKANILEA_ANONYMIZATION_KEY",
)


def _resolve_config_object() -> Any:
    import app.config as config_module

    for name in ("Config", "Settings", "AppConfig"):
        candidate = getattr(config_module, name, None)
        if (
            candidate is not None
            and hasattr(candidate, "CORE_DB")
            and hasattr(candidate, "AUTH_DB")
        ):
            return candidate
    if hasattr(config_module, "CORE_DB") and hasattr(config_module, "AUTH_DB"):
        return config_module
    raise RuntimeError("config_db_paths_missing")


def _resolve_config_db_paths() -> tuple[Path, Path]:
    cfg = _resolve_config_object()
    return Path(str(getattr(cfg, "CORE_DB"))), Path(str(getattr(cfg, "AUTH_DB")))


def _detect_read_only() -> bool:
    try:
        from app.license import load_runtime_license_state

        cfg = _resolve_config_object()
        state = load_runtime_license_state(
            license_path=Path(str(getattr(cfg, "LICENSE_PATH"))),
            trial_path=Path(str(getattr(cfg, "TRIAL_PATH"))),
            trial_days=int(getattr(cfg, "TRIAL_DAYS", 14)),
        )
        return bool(state.get("read_only", False))
    except Exception:
        return False


def _copy_db_with_sidecars(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        shutil.copy2(src, dst)
        for suffix in ("-wal", "-shm"):
            extra_src = Path(str(src) + suffix)
            extra_dst = Path(str(dst) + suffix)
            if extra_src.exists():
                shutil.copy2(extra_src, extra_dst)
        return
    con = sqlite3.connect(str(dst))
    con.close()


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@contextlib.contextmanager
def _sandbox_context(
    *,
    sandbox: bool,
    keep_artifacts: bool,
) -> Iterator[dict[str, Any]]:
    if not sandbox:
        core_db, auth_db = _resolve_config_db_paths()
        yield {
            "sandbox": False,
            "core_db": core_db,
            "auth_db": auth_db,
            "work_dir": None,
            "keep_artifacts": keep_artifacts,
        }
        return

    src_core_db, src_auth_db = _resolve_config_db_paths()
    work_dir = Path(tempfile.mkdtemp(prefix="kukanilea-ocrtest-"))
    sandbox_core_db = work_dir / "core.sqlite3"
    sandbox_auth_db = work_dir / "auth.sqlite3"
    _copy_db_with_sidecars(src_core_db, sandbox_core_db)
    _copy_db_with_sidecars(src_auth_db, sandbox_auth_db)

    previous_env = {key: os.environ.get(key) for key in ENV_DB_KEYS}
    os.environ["KUKANILEA_CORE_DB"] = str(sandbox_core_db)
    os.environ["KUKANILEA_AUTH_DB"] = str(sandbox_auth_db)
    os.environ["DB_FILENAME"] = str(sandbox_core_db)
    os.environ["TOPHANDWERK_DB_FILENAME"] = str(sandbox_core_db)
    os.environ.setdefault("KUKANILEA_ANONYMIZATION_KEY", "devtools-ocr-test-key")

    cfg = _resolve_config_object()
    old_cfg_core = getattr(cfg, "CORE_DB", None)
    old_cfg_auth = getattr(cfg, "AUTH_DB", None)
    setattr(cfg, "CORE_DB", sandbox_core_db)
    setattr(cfg, "AUTH_DB", sandbox_auth_db)

    old_core_db_path = Path(str(legacy_core.DB_PATH))
    try:
        legacy_core.set_db_path(sandbox_core_db)
    except Exception:
        legacy_core.DB_PATH = sandbox_core_db

    try:
        yield {
            "sandbox": True,
            "core_db": sandbox_core_db,
            "auth_db": sandbox_auth_db,
            "work_dir": work_dir,
            "keep_artifacts": keep_artifacts,
        }
    finally:
        try:
            legacy_core.set_db_path(old_core_db_path)
        except Exception:
            legacy_core.DB_PATH = old_core_db_path
        if old_cfg_core is not None:
            setattr(cfg, "CORE_DB", old_cfg_core)
        if old_cfg_auth is not None:
            setattr(cfg, "AUTH_DB", old_cfg_auth)
        _restore_env(previous_env)
        if not keep_artifacts:
            shutil.rmtree(work_dir, ignore_errors=True)


def _preflight_status(tenant_id: str) -> dict[str, Any]:
    from app.autonomy.ocr import ocr_allowed, resolve_tesseract_bin

    read_only = _detect_read_only()
    policy_enabled = bool(ocr_allowed(tenant_id))
    tesseract_found = resolve_tesseract_bin() is not None
    return {
        "policy_enabled": policy_enabled,
        "tesseract_found": tesseract_found,
        "read_only": read_only,
    }


def _write_test_image(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(TEST_IMAGE_PNG_B64))


def _query_latest_ocr_job(
    core_db_path: Path,
    tenant_id: str,
    basename: str,
) -> dict[str, Any] | None:
    con = sqlite3.connect(str(core_db_path))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            SELECT j.id, j.source_file_id, j.status, j.error_code, j.duration_ms,
                   j.chars_out, j.created_at
            FROM autonomy_ocr_jobs j
            JOIN source_files s ON s.id = j.source_file_id
            WHERE j.tenant_id=? AND s.tenant_id=? AND s.basename=?
            ORDER BY j.created_at DESC, j.id DESC
            LIMIT 1
            """,
            (tenant_id, tenant_id, basename),
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def _count_matches_knowledge(
    core_db_path: Path,
    tenant_id: str,
    patterns: list[str],
) -> int:
    con = sqlite3.connect(str(core_db_path))
    try:
        table_row = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_chunks' LIMIT 1"
        ).fetchone()
        if not table_row:
            return 0
        count = 0
        for pattern in patterns:
            row = con.execute(
                """
                SELECT COUNT(*) AS c
                FROM knowledge_chunks
                WHERE tenant_id=?
                  AND (instr(COALESCE(body,''), ?) > 0
                    OR instr(COALESCE(title,''), ?) > 0
                    OR instr(COALESCE(tags,''), ?) > 0)
                """,
                (tenant_id, pattern, pattern, pattern),
            ).fetchone()
            count += int((row or [0])[0] or 0)
        return count
    finally:
        con.close()


def _count_matches_eventlog(core_db_path: Path, patterns: list[str]) -> int:
    con = sqlite3.connect(str(core_db_path))
    try:
        total = 0
        table_exists = (
            con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events' LIMIT 1"
            ).fetchone()
            is not None
        )
        if not table_exists:
            return 0
        for pattern in patterns:
            row = con.execute(
                "SELECT COUNT(*) AS c FROM events WHERE instr(COALESCE(payload_json,''), ?) > 0",
                (pattern,),
            ).fetchone()
            total += int((row or [0])[0] or 0)
        return total
    finally:
        con.close()


def _execute_test_round(
    tenant_id: str,
    timeout_s: int,
    core_db_path: Path,
    artifacts_root: Path,
) -> dict[str, Any]:
    from app.autonomy.source_scan import (
        scan_sources_once,
        source_watch_config_get,
        source_watch_config_update,
    )

    cfg = source_watch_config_get(tenant_id, create_if_missing=True)
    documents_inbox_raw = str(cfg.get("documents_inbox_dir") or "").strip()
    if not documents_inbox_raw:
        documents_inbox = artifacts_root / "documents_inbox"
        source_watch_config_update(
            tenant_id,
            documents_inbox_dir=str(documents_inbox),
            enabled=True,
        )
    else:
        documents_inbox = Path(documents_inbox_raw)
    documents_inbox.mkdir(parents=True, exist_ok=True)

    basename = f"OCR_Test_2026-02-16_KD-9999_{uuid.uuid4().hex[:8]}.png"
    sample_path = artifacts_root / "sample_input.png"
    _write_test_image(sample_path)
    target_path = documents_inbox / basename
    shutil.copy2(sample_path, target_path)

    try:
        scan_sources_once(
            tenant_id,
            actor_user_id="devtools_ocr_test",
            budget_ms=max(1000, int(timeout_s * 1000)),
        )
        deadline = time.monotonic() + max(1, timeout_s)
        latest_job: dict[str, Any] | None = None
        while time.monotonic() <= deadline:
            latest_job = _query_latest_ocr_job(core_db_path, tenant_id, basename)
            if latest_job:
                break
            time.sleep(0.25)

        pii_patterns = [TEST_EMAIL_PATTERN, TEST_PHONE_PATTERN]
        pii_found_knowledge = (
            _count_matches_knowledge(core_db_path, tenant_id, pii_patterns) > 0
        )
        pii_found_eventlog = _count_matches_eventlog(core_db_path, pii_patterns) > 0

        return {
            "job_status": (str(latest_job.get("status") or "") if latest_job else None),
            "job_error_code": (
                str(latest_job.get("error_code") or "") if latest_job else None
            ),
            "duration_ms": (
                int(latest_job.get("duration_ms") or 0) if latest_job else None
            ),
            "chars_out": (
                int(latest_job.get("chars_out") or 0) if latest_job else None
            ),
            "truncated": False,
            "pii_found_knowledge": pii_found_knowledge,
            "pii_found_eventlog": pii_found_eventlog,
        }
    finally:
        with contextlib.suppress(Exception):
            target_path.unlink()


def _build_message(result: dict[str, Any]) -> str:
    if result.get("ok"):
        return "OCR test succeeded (policy, env, job, and PII checks passed)."
    reason = str(result.get("reason") or "failed")
    if reason == "policy_denied":
        return "OCR policy is disabled for tenant."
    if reason == "tesseract_missing":
        return "Tesseract binary not found or not allowlisted."
    if reason == "read_only":
        return "READ_ONLY active; skipping ingest/job run."
    if reason == "pii_leak":
        return "PII leak detected in Knowledge or Eventlog."
    if reason == "job_not_found":
        return "No OCR job was detected within timeout."
    return "OCR test failed."


def run_ocr_test(
    tenant_id: str,
    *,
    timeout_s: int = 10,
    sandbox: bool = True,
    keep_artifacts: bool = False,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip() or "default"
    result: dict[str, Any] = {
        "ok": False,
        "reason": None,
        "tenant_id": tenant,
        "sandbox": bool(sandbox),
        "policy_enabled": False,
        "tesseract_found": False,
        "read_only": False,
        "job_status": None,
        "job_error_code": None,
        "pii_found_knowledge": False,
        "pii_found_eventlog": False,
        "duration_ms": None,
        "chars_out": None,
        "truncated": False,
        "message": "",
    }

    try:
        with _sandbox_context(
            sandbox=bool(sandbox),
            keep_artifacts=bool(keep_artifacts),
        ) as ctx:
            preflight = _preflight_status(tenant)
            result["policy_enabled"] = bool(preflight["policy_enabled"])
            result["tesseract_found"] = bool(preflight["tesseract_found"])
            result["read_only"] = bool(preflight["read_only"])

            if result["read_only"]:
                result["reason"] = "read_only"
                result["message"] = _build_message(result)
                return result
            if not result["policy_enabled"]:
                result["reason"] = "policy_denied"
                result["message"] = _build_message(result)
                return result
            if not result["tesseract_found"]:
                result["reason"] = "tesseract_missing"
                result["message"] = _build_message(result)
                return result

            artifacts_root = Path(
                str(
                    ctx.get("work_dir")
                    or tempfile.mkdtemp(prefix="kukanilea-ocrtest-artifacts-")
                )
            )
            try:
                round_result = _execute_test_round(
                    tenant,
                    max(1, int(timeout_s)),
                    Path(str(ctx["core_db"])),
                    artifacts_root,
                )
            finally:
                if ctx.get("work_dir") is None and not keep_artifacts:
                    shutil.rmtree(artifacts_root, ignore_errors=True)

            result.update(round_result)

            pii_hit = bool(
                result["pii_found_knowledge"] or result["pii_found_eventlog"]
            )
            if pii_hit:
                result["reason"] = "pii_leak"
                result["ok"] = False
            elif not result["job_status"]:
                result["reason"] = "job_not_found"
                result["ok"] = False
            elif str(result["job_status"]).lower() != "done":
                code = str(result["job_error_code"] or "job_failed")
                result["reason"] = code
                result["ok"] = False
            else:
                result["ok"] = True
                result["reason"] = None

            result["message"] = _build_message(result)
            return result
    except Exception as exc:
        result["reason"] = "unexpected_error"
        result["message"] = (
            f"OCR test failed with unexpected error: {type(exc).__name__}"
        )
        result["ok"] = False
        return result
