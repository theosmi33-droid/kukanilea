from __future__ import annotations

import binascii
import contextlib
import os
import re
import shutil
import sqlite3
import struct
import tempfile
import time
import uuid
import zlib
from pathlib import Path
from typing import Any, Iterator

import kukanilea_core_v3_fixed as legacy_core
from app.devtools.ocr_policy import (
    ensure_watch_config_in_sandbox,
    get_policy_status,
)
from app.devtools.sandbox import (
    cleanup_sandbox,
    create_sandbox_copy,
    create_temp_inbox_dir,
    ensure_dir,
    resolve_core_db_path,
)
from app.devtools.tesseract_probe import probe_tesseract

TEST_EMAIL_PATTERN = "pilot+test@example.com"
TEST_PHONE_PATTERN = "+49 151 12345678"
TEST_IMAGE_TEXT_LINES = (
    "OCR SMOKE TEST 0123456789",
    "ABCXYZ OCR TEST",
)
MIN_TEST_IMAGE_BYTES = 10 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ENV_DB_KEYS = (
    "KUKANILEA_CORE_DB",
    "KUKANILEA_AUTH_DB",
    "DB_FILENAME",
    "TOPHANDWERK_DB_FILENAME",
    "KUKANILEA_ANONYMIZATION_KEY",
)
SAFE_PATH_RE = re.compile(r"[^\x20-\x7E]+")


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


def _sanitize_path_for_output(path: Path | str | None) -> str:
    text = (
        str(path or "").replace("\x00", "").replace("\r", "").replace("\n", "").strip()
    )
    if (
        text.startswith("/")
        or re.match(r"^[A-Za-z]:\\", text)
        or text.startswith("\\\\")
    ):
        return "<path>"
    text = SAFE_PATH_RE.sub("_", text)
    if len(text) > 256:
        text = text[-256:]
    return text


def _table_columns(core_db_path: Path, table: str) -> list[str]:
    con = sqlite3.connect(str(core_db_path))
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        return [str(row[1]) for row in rows]
    finally:
        con.close()


def _lookup_source_file_id(
    core_db_path: Path,
    tenant_id: str,
    *,
    path_hash: str,
    basename: str,
) -> tuple[str | None, str | None, list[str]]:
    columns = _table_columns(core_db_path, "source_files")
    if not columns:
        return None, "source_files_table_missing", []

    con = sqlite3.connect(str(core_db_path))
    con.row_factory = sqlite3.Row
    try:
        row = None
        if "path_hash" in columns:
            row = con.execute(
                """
                SELECT id
                FROM source_files
                WHERE tenant_id=? AND path_hash=?
                ORDER BY last_seen_at DESC, id DESC
                LIMIT 1
                """,
                (tenant_id, path_hash),
            ).fetchone()
        elif "basename" in columns:
            row = con.execute(
                """
                SELECT id
                FROM source_files
                WHERE tenant_id=? AND basename=?
                ORDER BY last_seen_at DESC, id DESC
                LIMIT 1
                """,
                (tenant_id, basename),
            ).fetchone()
        else:
            return None, "source_files_schema_unknown", columns
        return (str(row["id"]), None, columns) if row else (None, None, columns)
    finally:
        con.close()


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


def detect_read_only() -> bool:
    return _detect_read_only()


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
        core_db = resolve_core_db_path()
        _core_db_unused, auth_db = _resolve_config_db_paths()
        yield {
            "sandbox": False,
            "core_db": core_db,
            "auth_db": auth_db,
            "work_dir": None,
            "keep_artifacts": keep_artifacts,
        }
        return

    sandbox_core_db, work_dir = create_sandbox_copy("devtools")
    _core_db_unused, src_auth_db = _resolve_config_db_paths()
    sandbox_auth_db = work_dir / "auth.sqlite3"
    if src_auth_db.exists():
        shutil.copy2(src_auth_db, sandbox_auth_db)
    else:
        sqlite3.connect(str(sandbox_auth_db)).close()

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
            cleanup_sandbox(work_dir)


@contextlib.contextmanager
def _db_override_context(db_path: Path) -> Iterator[dict[str, Any]]:
    override_db = Path(str(db_path))
    _core_db_unused, current_auth_db = _resolve_config_db_paths()
    previous_env = {key: os.environ.get(key) for key in ENV_DB_KEYS}
    os.environ["KUKANILEA_CORE_DB"] = str(override_db)
    os.environ["DB_FILENAME"] = str(override_db)
    os.environ["TOPHANDWERK_DB_FILENAME"] = str(override_db)
    os.environ.setdefault("KUKANILEA_ANONYMIZATION_KEY", "devtools-ocr-test-key")

    cfg = _resolve_config_object()
    old_cfg_core = getattr(cfg, "CORE_DB", None)
    old_cfg_auth = getattr(cfg, "AUTH_DB", None)
    setattr(cfg, "CORE_DB", override_db)
    setattr(cfg, "AUTH_DB", current_auth_db)

    old_core_db_path = Path(str(legacy_core.DB_PATH))
    try:
        legacy_core.set_db_path(override_db)
    except Exception:
        legacy_core.DB_PATH = override_db

    try:
        yield {
            "sandbox": False,
            "core_db": override_db,
            "auth_db": current_auth_db,
            "work_dir": None,
            "keep_artifacts": False,
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


GLYPH_5X7: dict[str, tuple[str, ...]] = {
    " ": ("00000",) * 7,
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", binascii.crc32(tag + payload) & 0xFFFFFFFF)
    )


def _build_test_png_bytes() -> bytes:
    width = 1200
    height = 320
    pixels = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            pixels[y * width + x] = 230 + ((x * 17 + y * 31 + (x * y) % 97) % 25)

    scale = 8
    x0 = 40
    y0 = 50
    line_gap = 26
    for line_idx, line in enumerate(TEST_IMAGE_TEXT_LINES):
        line_upper = str(line).upper()
        y_base = y0 + line_idx * (7 * scale + line_gap)
        x = x0
        for char in line_upper:
            glyph = GLYPH_5X7.get(char, GLYPH_5X7[" "])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit != "1":
                        continue
                    px_start = x + gx * scale
                    py_start = y_base + gy * scale
                    for dy in range(scale):
                        py = py_start + dy
                        if py < 0 or py >= height:
                            continue
                        row_start = py * width
                        for dx in range(scale):
                            px = px_start + dx
                            if 0 <= px < width:
                                pixels[row_start + px] = 0
            x += (5 * scale) + 4

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * width
        raw.extend(pixels[start : start + width])
    compressed = zlib.compress(bytes(raw), level=9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _write_test_image(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(_build_test_png_bytes())


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
    *,
    inbox_dir_override: Path | None = None,
    direct_submit_in_sandbox: bool = False,
    tesseract_lang: str | None = None,
    tesseract_tessdata_dir: str | None = None,
    tesseract_bin: str | None = None,
    retry_enabled: bool = True,
) -> dict[str, Any]:
    from app.autonomy.ocr import submit_ocr_for_source_file
    from app.autonomy.source_scan import (
        hmac_path_hash,
        scan_sources_once,
        source_watch_config_get,
        source_watch_config_update,
    )

    if inbox_dir_override is not None:
        documents_inbox = ensure_dir(Path(str(inbox_dir_override)))
    else:
        cfg = source_watch_config_get(tenant_id, create_if_missing=True)
        documents_inbox_raw = str(cfg.get("documents_inbox_dir") or "").strip()
        if not documents_inbox_raw:
            documents_inbox = ensure_dir(artifacts_root / "documents_inbox")
            source_watch_config_update(
                tenant_id,
                documents_inbox_dir=str(documents_inbox),
                enabled=True,
            )
        else:
            documents_inbox = ensure_dir(Path(documents_inbox_raw))

    basename = f"OCR_Test_2026-02-16_KD-9999_{uuid.uuid4().hex[:8]}.png"
    sample_path = artifacts_root / "sample_input.png"
    _write_test_image(sample_path)
    sample_bytes = sample_path.read_bytes()
    if not sample_bytes.startswith(PNG_SIGNATURE):
        return {
            "job_status": None,
            "job_error_code": None,
            "duration_ms": None,
            "chars_out": None,
            "truncated": False,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "inbox_dir_used": _sanitize_path_for_output(documents_inbox),
            "scanner_discovered_files": 0,
            "direct_submit_used": False,
            "source_lookup_reason": None,
            "source_files_columns": None,
            "round_reason": "test_image_invalid",
        }
    if len(sample_bytes) < MIN_TEST_IMAGE_BYTES:
        return {
            "job_status": None,
            "job_error_code": None,
            "duration_ms": None,
            "chars_out": None,
            "truncated": False,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "inbox_dir_used": _sanitize_path_for_output(documents_inbox),
            "scanner_discovered_files": 0,
            "direct_submit_used": False,
            "source_lookup_reason": None,
            "source_files_columns": None,
            "round_reason": "input_too_small",
        }
    target_path = documents_inbox / basename
    shutil.copy2(sample_path, target_path)

    try:
        scan_summary = scan_sources_once(
            tenant_id,
            actor_user_id="devtools_ocr_test",
            budget_ms=max(1000, int(timeout_s * 1000)),
        )
        scanner_discovered_files = int(scan_summary.get("discovered") or 0)
        deadline = time.monotonic() + max(1, timeout_s)
        latest_job: dict[str, Any] | None = None
        while time.monotonic() <= deadline:
            latest_job = _query_latest_ocr_job(core_db_path, tenant_id, basename)
            if latest_job:
                break
            time.sleep(0.25)

        direct_submit_used = False
        source_lookup_reason: str | None = None
        source_columns: list[str] | None = None
        if latest_job is None and bool(direct_submit_in_sandbox):
            source_file_id, source_lookup_reason, source_columns = (
                _lookup_source_file_id(
                    core_db_path,
                    tenant_id,
                    path_hash=hmac_path_hash(str(target_path)),
                    basename=basename,
                )
            )
            if source_file_id:
                try:
                    submit_ocr_for_source_file(
                        tenant_id,
                        actor_user_id="devtools_ocr_test",
                        source_file_id=source_file_id,
                        abs_path=target_path,
                        lang_override=tesseract_lang,
                        tessdata_dir=tesseract_tessdata_dir,
                        tesseract_bin_override=tesseract_bin,
                        allow_retry=retry_enabled,
                    )
                    direct_submit_used = True
                except Exception:
                    source_lookup_reason = "direct_submit_failed"

            deadline = time.monotonic() + max(1, timeout_s)
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
            "inbox_dir_used": _sanitize_path_for_output(documents_inbox),
            "scanner_discovered_files": scanner_discovered_files,
            "direct_submit_used": direct_submit_used,
            "source_lookup_reason": source_lookup_reason,
            "source_files_columns": source_columns,
            "round_reason": None,
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
    if reason == "tessdata_missing":
        return "Tesseract data files were not found."
    if reason == "language_missing":
        return "Requested OCR language is unavailable."
    if reason == "tesseract_failed":
        return "Tesseract execution failed."
    if reason == "config_file_missing":
        return "Tesseract config file could not be loaded."
    if reason == "tesseract_warning":
        return "Tesseract reported warnings and strict mode is enabled."
    if reason == "read_only":
        return "READ_ONLY active; skipping ingest/job run."
    if reason == "pii_leak":
        return "PII leak detected in Knowledge or Eventlog."
    if reason == "job_not_found":
        return "No OCR job was detected within timeout."
    if reason == "schema_unknown":
        return "Policy schema is unknown. Inspect existing_columns."
    if reason == "ambiguous_columns":
        return "Multiple OCR policy columns detected; choose one explicitly."
    if reason == "schema_unknown_insert":
        return "Policy row insert failed due to unknown required columns."
    if reason == "watch_config_table_missing":
        return "Watch configuration table is missing in the selected database."
    if reason == "source_files_table_missing":
        return "Source files table is missing in the selected database."
    if reason == "source_files_schema_unknown":
        return "Source files lookup schema is unknown."
    if reason == "failed":
        return "OCR command failed for the test image."
    if reason == "timeout":
        return "OCR run timed out."
    if reason == "input_too_small":
        return "Embedded OCR smoke image is unexpectedly small."
    if reason == "test_image_invalid":
        return "Embedded OCR smoke image is invalid."
    return "OCR test failed."


def _next_actions_for_reason(reason: str | None) -> list[str]:
    key = str(reason or "")
    mapping = {
        "policy_denied": [
            "Enable OCR policy for this tenant (use --enable-policy-in-sandbox or update knowledge_source_policies).",
            "Verify tenant_id is correct.",
        ],
        "tesseract_missing": [
            "Install tesseract and ensure it is on PATH (e.g. /opt/homebrew/bin/tesseract).",
            "Re-run with --json and confirm tesseract_found=true.",
            "If --tesseract-bin is used, ensure the path exists and is executable.",
        ],
        "tessdata_missing": [
            "Set --tessdata-dir explicitly and verify traineddata files exist.",
            "Run --show-tesseract to inspect sanitized diagnostics.",
        ],
        "language_missing": [
            "Requested OCR language is unavailable in tessdata.",
            "Use --lang with an available language from --show-tesseract.",
        ],
        "tesseract_failed": [
            "Verify tesseract binary execution and local language data installation.",
            "Re-run with --show-tesseract for sanitized stderr diagnostics.",
        ],
        "config_file_missing": [
            "Tesseract reported a missing config file (read_params_file / config).",
            "Verify installation and rerun with explicit --tessdata-dir.",
        ],
        "tesseract_warning": [
            "Tesseract emitted warnings; verify tessdata and language packs.",
            "Disable strict mode or fix warnings, then re-run OCR smoke.",
        ],
        "read_only": [
            "Disable READ_ONLY for dev testing or run without --enable-policy-in-sandbox.",
            "Re-run after changing READ_ONLY.",
        ],
        "schema_unknown": [
            "Inspect table schema: knowledge_source_policies columns listed in existing_columns.",
            "Update allowlist or schema handler accordingly.",
        ],
        "ambiguous_columns": [
            "Use a single OCR policy column from the allowlist (allow_ocr/ocr_enabled/ocr_allowed).",
            "Adjust schema handler to resolve ambiguity explicitly.",
        ],
        "schema_unknown_insert": [
            "Inspect required columns for knowledge_source_policies in existing_columns.",
            "Extend insert defaults for missing required fields before enabling policy.",
        ],
        "watch_config_table_missing": [
            "Initialize autonomy tables so source_watch_config exists.",
            "Re-run with --show-policy to verify schema and then retry OCR smoke.",
        ],
        "source_files_table_missing": [
            "Initialize autonomy scanner tables before OCR smoke.",
            "Re-run scanner once and retry with --direct-submit-in-sandbox if needed.",
        ],
        "source_files_schema_unknown": [
            "Inspect source_files schema and ensure path_hash or basename column exists.",
            "Update lookup handler for current schema.",
        ],
        "timeout": [
            "Increase --timeout.",
            "Check scanner paths / source_watch_config and that the inbox dir is writable.",
        ],
        "job_not_found": [
            "Use --seed-watch-config-in-sandbox so the scanner sees a deterministic inbox.",
            "Retry with --direct-submit-in-sandbox to trigger OCR directly after scan.",
        ],
        "failed": [
            "Verify local tesseract language data and binary execution for image OCR.",
            "Retry with --direct-submit-in-sandbox and inspect job_error_code.",
        ],
        "input_too_small": [
            "Regenerate the embedded OCR smoke image; current sample is too small.",
            "Run tests to ensure image generation and sanity checks are in sync.",
        ],
        "test_image_invalid": [
            "Regenerate the embedded OCR smoke image; PNG signature check failed.",
            "Verify image creation path before scanner execution.",
        ],
        "pii_leak": [
            "Stop: redaction regression suspected.",
            "Check OCR redaction pipeline and eventlog filters; do not proceed to pilot.",
        ],
    }
    return list(mapping.get(key, []))


def next_actions_for_reason(reason: str | None) -> list[str]:
    return _next_actions_for_reason(reason)


def run_ocr_test(
    tenant_id: str,
    *,
    timeout_s: int = 10,
    sandbox: bool = True,
    keep_artifacts: bool = False,
    db_path_override: Path | None = None,
    seed_watch_config_in_sandbox: bool = False,
    direct_submit_in_sandbox: bool = False,
    tessdata_dir: str | None = None,
    tesseract_bin: str | None = None,
    lang: str | None = None,
    strict: bool = False,
    retry_enabled: bool = True,
) -> dict[str, Any]:
    tenant = str(tenant_id or "").strip() or "default"
    sandbox_like = bool(sandbox or db_path_override is not None)
    result: dict[str, Any] = {
        "ok": False,
        "reason": None,
        "tenant_id": tenant,
        "sandbox": bool(sandbox),
        "policy_enabled": False,
        "policy_enabled_base": None,
        "policy_enabled_effective": None,
        "policy_reason": None,
        "existing_columns": None,
        "tesseract_found": False,
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
        # Aliases kept for operator-facing schema compatibility.
        "tessdata_prefix_used": None,
        "lang_used": None,
        "probe_reason": None,
        "probe_next_actions": [],
        "stderr_tail": None,
        "strict_mode": bool(strict),
        "retry_enabled": bool(retry_enabled),
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
        "next_actions": [],
        "message": "",
    }

    try:
        if db_path_override is not None:
            cm = _db_override_context(Path(str(db_path_override)))
        else:
            cm = _sandbox_context(
                sandbox=bool(sandbox),
                keep_artifacts=bool(keep_artifacts),
            )
        with cm as ctx:
            result["sandbox"] = bool(sandbox and db_path_override is None)
            core_db_path = Path(str(ctx["core_db"]))
            if result["sandbox"]:
                result["sandbox_db_path"] = str(core_db_path)

            try:
                from app.autonomy.ocr import resolve_tesseract_bin

                resolved_bin = resolve_tesseract_bin()
                resolved_bin_str = str(resolved_bin) if resolved_bin else None
            except Exception:
                resolved_bin_str = None
            preferred_langs = [str(lang).strip()] if str(lang or "").strip() else None
            probe = probe_tesseract(
                bin_path=str(tesseract_bin or "").strip() or resolved_bin_str,
                tessdata_dir=tessdata_dir,
                preferred_langs=preferred_langs,
            )
            result["tesseract_found"] = bool(
                probe.get("tesseract_found") or probe.get("bin_path")
            )
            result["tessdata_dir"] = (
                _sanitize_path_for_output(
                    probe.get("tessdata_prefix")
                    or probe.get("tessdata_dir_used")
                    or probe.get("tessdata_dir")
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
                _sanitize_path_for_output(item)
                for item in list(probe.get("tessdata_candidates") or [])
            ]
            result["print_tessdata_dir"] = (
                _sanitize_path_for_output(probe.get("print_tessdata_dir")) or None
            )
            result["tesseract_bin_used"] = (
                _sanitize_path_for_output(
                    probe.get("tesseract_bin_used") or probe.get("bin_path")
                )
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
            result["tesseract_probe_next_actions"] = [
                str(item) for item in list(probe.get("next_actions") or [])
            ]
            result["tesseract_stderr_tail"] = (
                str(probe.get("stderr_tail") or "") or None
            )
            result["tessdata_prefix_used"] = result["tessdata_dir"]
            result["lang_used"] = result["tesseract_lang_used"]
            result["probe_reason"] = result["tesseract_probe_reason"]
            result["probe_next_actions"] = list(result["tesseract_probe_next_actions"])
            result["stderr_tail"] = result["tesseract_stderr_tail"]

            policy_status = get_policy_status(tenant, db_path=core_db_path)
            if bool(policy_status.get("ok")):
                result["policy_enabled_effective"] = bool(
                    policy_status.get("policy_enabled")
                )
                result["existing_columns"] = list(
                    policy_status.get("existing_columns") or []
                )
            else:
                result["policy_reason"] = str(
                    policy_status.get("reason") or "schema_unknown"
                )
                result["existing_columns"] = list(
                    policy_status.get("existing_columns") or []
                )

            preflight = _preflight_status(tenant)
            result["policy_enabled"] = bool(preflight["policy_enabled"])
            result["read_only"] = bool(preflight["read_only"])
            if result["policy_enabled_effective"] is None:
                result["policy_enabled_effective"] = bool(result["policy_enabled"])

            if result["read_only"]:
                result["reason"] = "read_only"
                result["message"] = _build_message(result)
                result["next_actions"] = _next_actions_for_reason(
                    str(result.get("reason") or "")
                )
                return result
            if result["policy_reason"]:
                result["reason"] = str(result["policy_reason"])
                result["message"] = _build_message(result)
                result["next_actions"] = _next_actions_for_reason(
                    str(result.get("reason") or "")
                )
                return result
            if result["tesseract_probe_reason"] in {
                "tesseract_missing",
                "tessdata_missing",
                "language_missing",
                "tesseract_failed",
            }:
                result["reason"] = str(result["tesseract_probe_reason"])
                result["message"] = _build_message(result)
                result["next_actions"] = list(result["tesseract_probe_next_actions"])
                if not result["next_actions"]:
                    result["next_actions"] = _next_actions_for_reason(
                        str(result.get("reason") or "")
                    )
                return result
            if bool(strict) and result["tesseract_probe_reason"] == "ok_with_warnings":
                result["reason"] = "tesseract_warning"
                result["message"] = _build_message(result)
                result["next_actions"] = _next_actions_for_reason("tesseract_warning")
                return result
            if not result["policy_enabled"]:
                result["reason"] = "policy_denied"
                result["message"] = _build_message(result)
                result["next_actions"] = _next_actions_for_reason(
                    str(result.get("reason") or "")
                )
                return result
            if not result["tesseract_found"]:
                result["reason"] = "tesseract_missing"
                result["message"] = _build_message(result)
                result["next_actions"] = _next_actions_for_reason(
                    str(result.get("reason") or "")
                )
                return result

            inbox_dir_override: Path | None = None
            if bool(seed_watch_config_in_sandbox) and sandbox_like:
                sandbox_root = Path(str(ctx.get("work_dir") or core_db_path.parent))
                inbox_dir = create_temp_inbox_dir(sandbox_root)
                ensure_dir(inbox_dir)
                watch_seed = ensure_watch_config_in_sandbox(
                    tenant,
                    sandbox_db_path=core_db_path,
                    inbox_dir=str(inbox_dir),
                )
                result["inbox_dir_used"] = _sanitize_path_for_output(inbox_dir)
                if not bool(watch_seed.get("ok")):
                    result["reason"] = str(
                        watch_seed.get("reason") or "watch_config_table_missing"
                    )
                    result["existing_columns"] = list(
                        watch_seed.get("existing_columns")
                        or result.get("existing_columns")
                        or []
                    )
                    result["message"] = _build_message(result)
                    result["next_actions"] = _next_actions_for_reason(
                        str(result.get("reason") or "")
                    )
                    return result
                result["watch_config_seeded"] = bool(watch_seed.get("seeded"))
                result["watch_config_existed"] = bool(watch_seed.get("existed_before"))
                inbox_dir_override = inbox_dir

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
                    core_db_path,
                    artifacts_root,
                    inbox_dir_override=inbox_dir_override,
                    direct_submit_in_sandbox=bool(
                        direct_submit_in_sandbox and sandbox_like
                    ),
                    tesseract_lang=result.get("tesseract_lang_used"),
                    tesseract_tessdata_dir=(
                        str(
                            probe.get("tessdata_prefix")
                            or probe.get("tessdata_dir_used")
                            or probe.get("tessdata_dir")
                            or ""
                        )
                        or None
                    ),
                    tesseract_bin=(
                        str(
                            probe.get("tesseract_bin_used")
                            or probe.get("bin_path")
                            or ""
                        )
                        or None
                    ),
                    retry_enabled=bool(retry_enabled),
                )
            finally:
                if ctx.get("work_dir") is None and not keep_artifacts:
                    shutil.rmtree(artifacts_root, ignore_errors=True)

            result.update(round_result)
            if round_result.get("round_reason"):
                result["reason"] = str(round_result.get("round_reason") or "failed")
                result["ok"] = False
                result["message"] = _build_message(result)
                result["next_actions"] = _next_actions_for_reason(
                    str(result.get("reason") or "")
                )
                return result

            pii_hit = bool(
                result["pii_found_knowledge"] or result["pii_found_eventlog"]
            )
            if pii_hit:
                result["reason"] = "pii_leak"
                result["ok"] = False
            elif not result["job_status"]:
                lookup_reason = str(result.get("source_lookup_reason") or "")
                if lookup_reason in {
                    "source_files_table_missing",
                    "source_files_schema_unknown",
                }:
                    result["reason"] = lookup_reason
                else:
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
            result["next_actions"] = _next_actions_for_reason(
                str(result.get("reason") or "")
            )
            return result
    except Exception as exc:
        result["reason"] = "unexpected_error"
        result["message"] = (
            f"OCR test failed with unexpected error: {type(exc).__name__}"
        )
        result["ok"] = False
        result["next_actions"] = _next_actions_for_reason(
            str(result.get("reason") or "")
        )
        return result
