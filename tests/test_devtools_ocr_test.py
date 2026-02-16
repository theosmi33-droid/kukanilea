from __future__ import annotations

import contextlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

import app.devtools.cli_ocr_test as cli_ocr_test
import app.devtools.ocr_test as ocr_test


@contextlib.contextmanager
def _dummy_ctx():
    yield {
        "sandbox": False,
        "core_db": Path("/tmp/core.sqlite3"),
        "auth_db": Path("/tmp/auth.sqlite3"),
        "work_dir": None,
        "keep_artifacts": False,
    }


def _policy_ok(enabled: bool = True) -> dict[str, object]:
    return {
        "ok": True,
        "policy_enabled": enabled,
        "ocr_column": "allow_ocr",
        "row_present": True,
        "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
        "table": "knowledge_source_policies",
    }


@pytest.fixture(autouse=True)
def _default_probe(monkeypatch):
    monkeypatch.setattr(
        ocr_test,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": None,
            "tesseract_found": True,
            "bin_path": "/usr/bin/tesseract",
            "tesseract_bin_used": "/usr/bin/tesseract",
            "print_tessdata_dir": "/usr/share/tessdata",
            "tessdata_prefix": "/usr/share",
            "tessdata_dir_used": "/usr/share",
            "tessdata_dir": "/usr/share",
            "tessdata_source": "heuristic",
            "tessdata_candidates": ["/usr/share"],
            "langs": ["eng", "deu"],
            "lang_selected": "eng",
            "lang_used": "eng",
            "warnings": [],
            "stderr_tail": None,
            "next_actions": [],
        },
    )


def test_run_ocr_test_policy_denied(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(False)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": False,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "policy_denied"
    assert result["tesseract_found"] is True
    assert result["tesseract_lang_used"] == "eng"
    assert result["tesseract_probe_reason"] is None


def test_run_ocr_test_probe_failure_tessdata(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": False,
            "reason": "tessdata_missing",
            "bin_path": "/usr/bin/tesseract",
            "tessdata_dir": None,
            "tessdata_source": None,
            "langs": [],
            "lang_used": None,
            "stderr_tail": "Error opening data file <path>/eng.traineddata",
            "next_actions": ["Set --tessdata-dir explicitly."],
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_a, **_k: _policy_ok(True)
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "tessdata_missing"
    assert result["tesseract_probe_reason"] == "tessdata_missing"
    assert result["next_actions"]


def test_run_ocr_test_strict_rejects_probe_warnings(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok_with_warnings",
            "tesseract_found": True,
            "bin_path": "/usr/bin/tesseract",
            "tessdata_prefix": "/usr/share",
            "tessdata_dir_used": "/usr/share",
            "tessdata_source": "heuristic",
            "langs": ["deu", "osd"],
            "lang_selected": "deu",
            "warnings": ["Error opening data file <path>/eng.traineddata"],
            "stderr_tail": "Error opening data file <path>/eng.traineddata",
            "next_actions": ["warning"],
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False, strict=True)
    assert result["ok"] is False
    assert result["reason"] == "tesseract_warning"


def test_run_ocr_test_passes_tesseract_bin_override(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": False,
            "tesseract_found": False,
            "read_only": False,
        },
    )

    captured: dict[str, object] = {}

    def _probe(**kwargs):
        captured["bin_path"] = kwargs.get("bin_path")
        return {
            "ok": False,
            "reason": "tesseract_missing",
            "tesseract_found": False,
            "bin_path": None,
            "tessdata_dir": None,
            "tessdata_source": None,
            "langs": [],
            "lang_used": None,
            "stderr_tail": None,
            "next_actions": ["Install tesseract and ensure it is on PATH."],
        }

    monkeypatch.setattr(ocr_test, "probe_tesseract", _probe)
    result = ocr_test.run_ocr_test(
        "TENANT_A",
        sandbox=False,
        tesseract_bin="/tmp/custom-tesseract",
    )
    assert result["ok"] is False
    assert result["reason"] == "tesseract_missing"
    assert captured["bin_path"] == "/tmp/custom-tesseract"


def test_run_ocr_test_tesseract_missing(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": False,
            "reason": "tesseract_missing",
            "bin_path": None,
            "tessdata_dir": None,
            "tessdata_source": None,
            "langs": [],
            "lang_used": None,
            "stderr_tail": None,
            "next_actions": ["Install tesseract and ensure it is on PATH."],
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": False,
            "read_only": False,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "tesseract_missing"


def test_run_ocr_test_tesseract_not_allowlisted(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": False,
            "reason": "tesseract_not_allowlisted",
            "tesseract_found": True,
            "tesseract_allowlisted": False,
            "tesseract_allowlist_reason": "outside_allowed_prefixes",
            "tesseract_allowed_prefixes": ["/opt/homebrew", "/usr/local/bin"],
            "bin_path": "/tmp/tesseract",
            "tessdata_dir": None,
            "tessdata_source": None,
            "langs": [],
            "lang_used": None,
            "stderr_tail": None,
            "next_actions": ["Use allowlisted prefix."],
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": False,
            "read_only": False,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "tesseract_not_allowlisted"
    assert result["tesseract_allowlisted"] is False
    assert result["tesseract_allowlist_reason"] == "outside_allowed_prefixes"
    assert result["tesseract_allowed_prefixes"]
    assert any("allowlist" in str(item).lower() for item in result["next_actions"])


def test_run_ocr_test_uses_probe_bin_path_for_job(monkeypatch) -> None:
    import app.autonomy.ocr as autonomy_ocr

    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok",
            "tesseract_found": True,
            "tesseract_allowlisted": True,
            "tesseract_allowlist_reason": "matched_prefix",
            "tesseract_allowed_prefixes": ["/opt/homebrew"],
            "bin_path": "/opt/homebrew/bin/tesseract",
            "tesseract_bin_used": "<path>",
            "tessdata_prefix": "/opt/homebrew/share",
            "tessdata_dir_used": "/opt/homebrew/share",
            "tessdata_source": "cli",
            "langs": ["eng"],
            "lang_selected": "eng",
            "warnings": [],
            "stderr_tail": None,
            "next_actions": [],
        },
    )
    monkeypatch.setattr(
        autonomy_ocr,
        "resolve_tesseract_binary",
        lambda **_kwargs: type(
            "Resolved",
            (),
            {
                "resolved_path": "/opt/homebrew/bin/tesseract",
                "resolution_source": "path",
                "allowlisted": True,
                "allowlist_reason": "matched_prefix",
            },
        )(),
    )
    captured: dict[str, object] = {}

    def _round(*_args, **kwargs):
        captured["tesseract_bin"] = kwargs.get("tesseract_bin")
        return {
            "job_status": "done",
            "job_error_code": None,
            "duration_ms": 5,
            "chars_out": 12,
            "truncated": False,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "inbox_dir_used": "/tmp/inbox",
            "scanner_discovered_files": 1,
            "direct_submit_used": True,
            "source_lookup_reason": None,
            "source_files_columns": None,
            "tesseract_exec_errno": None,
        }

    monkeypatch.setattr(ocr_test, "_execute_test_round", _round)

    result = ocr_test.run_ocr_test(
        "TENANT_A",
        sandbox=False,
        direct_submit_in_sandbox=True,
    )
    assert result["ok"] is True
    assert captured["tesseract_bin"] == "/opt/homebrew/bin/tesseract"
    assert result["tesseract_bin_used_probe"] == "<path>"
    assert result["tesseract_bin_used_job"] == "<path>"


def test_run_ocr_test_read_only(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": True,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "read_only"


def test_run_ocr_test_success_path(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_execute_test_round",
        lambda *_args, **_kwargs: {
            "job_status": "done",
            "job_error_code": None,
            "duration_ms": 120,
            "chars_out": 1400,
            "truncated": False,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is True
    assert result["reason"] is None
    assert result["job_status"] == "done"


def test_run_ocr_test_pii_leak_knowledge(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_execute_test_round",
        lambda *_args, **_kwargs: {
            "job_status": "done",
            "job_error_code": None,
            "duration_ms": 150,
            "chars_out": 1000,
            "truncated": False,
            "pii_found_knowledge": True,
            "pii_found_eventlog": False,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "pii_leak"
    assert result["pii_found_knowledge"] is True


def test_run_ocr_test_pii_leak_eventlog(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_execute_test_round",
        lambda *_args, **_kwargs: {
            "job_status": "done",
            "job_error_code": None,
            "duration_ms": 150,
            "chars_out": 1000,
            "truncated": False,
            "pii_found_knowledge": False,
            "pii_found_eventlog": True,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "pii_leak"
    assert result["pii_found_eventlog"] is True


def test_run_ocr_test_sandbox_cleanup_on_exception(tmp_path: Path, monkeypatch) -> None:
    src_core = tmp_path / "src-core.sqlite3"
    src_auth = tmp_path / "src-auth.sqlite3"
    sqlite3.connect(str(src_core)).close()
    sqlite3.connect(str(src_auth)).close()

    sandbox_dir = tmp_path / "sandbox-dir"

    def _fake_mkdtemp(prefix: str) -> str:
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        return str(sandbox_dir)

    monkeypatch.setattr(
        ocr_test, "_resolve_config_db_paths", lambda: (src_core, src_auth)
    )
    monkeypatch.setattr(ocr_test.tempfile, "mkdtemp", _fake_mkdtemp)
    monkeypatch.setattr(ocr_test.legacy_core, "set_db_path", lambda _path: None)
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ocr_test, "_execute_test_round", _raise)
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=True, keep_artifacts=False)
    assert result["ok"] is False
    assert result["reason"] == "unexpected_error"
    assert not sandbox_dir.exists()


def test_run_ocr_test_schema_unknown(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test,
        "get_policy_status",
        lambda *_args, **_kwargs: {
            "ok": False,
            "reason": "schema_unknown",
            "existing_columns": ["tenant_id", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": False,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert result["ok"] is False
    assert result["reason"] == "schema_unknown"
    assert result["existing_columns"] == ["tenant_id", "updated_at"]


def test_run_ocr_test_watch_config_seed_failure(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test, "create_temp_inbox_dir", lambda _root: Path("/tmp/inbox")
    )
    monkeypatch.setattr(ocr_test, "ensure_dir", lambda p: Path(str(p)))
    monkeypatch.setattr(
        ocr_test,
        "ensure_watch_config_in_sandbox",
        lambda *_args, **_kwargs: {
            "ok": False,
            "reason": "watch_config_table_missing",
            "table": "source_watch_config",
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_execute_test_round",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    result = ocr_test.run_ocr_test(
        "TENANT_A",
        sandbox=False,
        db_path_override=Path("/tmp/core.sqlite3"),
        seed_watch_config_in_sandbox=True,
    )
    assert result["ok"] is False
    assert result["reason"] == "watch_config_table_missing"


def test_run_ocr_test_passes_direct_submit_only_when_requested(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test, "create_temp_inbox_dir", lambda _root: Path("/tmp/inbox")
    )
    monkeypatch.setattr(ocr_test, "ensure_dir", lambda p: Path(str(p)))
    monkeypatch.setattr(
        ocr_test,
        "ensure_watch_config_in_sandbox",
        lambda *_args, **_kwargs: {
            "ok": True,
            "seeded": True,
            "existed_before": False,
            "inbox_dir": "/tmp/inbox",
            "used_column": "documents_inbox_dir",
        },
    )
    captured: dict[str, object] = {}

    def _round(*_args, **kwargs):
        captured["direct_submit_in_sandbox"] = kwargs.get("direct_submit_in_sandbox")
        captured["retry_enabled"] = kwargs.get("retry_enabled")
        return {
            "job_status": "done",
            "job_error_code": None,
            "duration_ms": 10,
            "chars_out": 100,
            "truncated": False,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "inbox_dir_used": "/tmp/inbox",
            "scanner_discovered_files": 1,
            "direct_submit_used": True,
            "source_lookup_reason": None,
            "source_files_columns": ["id", "tenant_id", "path_hash", "basename"],
        }

    monkeypatch.setattr(ocr_test, "_execute_test_round", _round)
    result = ocr_test.run_ocr_test(
        "TENANT_A",
        sandbox=False,
        db_path_override=Path("/tmp/core.sqlite3"),
        seed_watch_config_in_sandbox=True,
        direct_submit_in_sandbox=True,
        retry_enabled=False,
    )
    assert result["ok"] is True
    assert result["watch_config_seeded"] is True
    assert captured["direct_submit_in_sandbox"] is True
    assert captured["retry_enabled"] is False


def test_run_ocr_test_read_only_blocks_seed_and_direct_submit(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": True,
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "ensure_watch_config_in_sandbox",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not seed")
        ),
    )
    monkeypatch.setattr(
        ocr_test,
        "_execute_test_round",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    result = ocr_test.run_ocr_test(
        "TENANT_A",
        sandbox=False,
        db_path_override=Path("/tmp/core.sqlite3"),
        seed_watch_config_in_sandbox=True,
        direct_submit_in_sandbox=True,
    )
    assert result["ok"] is False
    assert result["reason"] == "read_only"


def test_run_ocr_test_output_does_not_echo_test_pii(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
    )
    monkeypatch.setattr(
        ocr_test,
        "_preflight_status",
        lambda _tenant: {
            "policy_enabled": True,
            "tesseract_found": True,
            "read_only": False,
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "_execute_test_round",
        lambda *_args, **_kwargs: {
            "job_status": "done",
            "job_error_code": None,
            "duration_ms": 20,
            "chars_out": 120,
            "truncated": False,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "inbox_dir_used": "/tmp/inbox",
            "scanner_discovered_files": 1,
            "direct_submit_used": False,
            "source_lookup_reason": None,
            "source_files_columns": None,
        },
    )
    result = ocr_test.run_ocr_test("TENANT_A", sandbox=False)
    assert ocr_test.TEST_EMAIL_PATTERN not in str(result.get("message") or "")
    assert ocr_test.TEST_PHONE_PATTERN not in str(result.get("message") or "")
    for item in result.get("next_actions") or []:
        assert ocr_test.TEST_EMAIL_PATTERN not in str(item)
        assert ocr_test.TEST_PHONE_PATTERN not in str(item)


def test_preflight_reports_tesseract_even_when_policy_denied(monkeypatch) -> None:
    import app.autonomy.ocr as autonomy_ocr

    monkeypatch.setattr(autonomy_ocr, "ocr_allowed", lambda _tenant: False)
    monkeypatch.setattr(
        autonomy_ocr,
        "resolve_tesseract_bin",
        lambda: Path("/opt/homebrew/bin/tesseract"),
    )
    monkeypatch.setattr(ocr_test, "_detect_read_only", lambda: False)

    result = ocr_test._preflight_status("dev")
    assert result["policy_enabled"] is False
    assert result["tesseract_found"] is True
    assert result["read_only"] is False


def test_cli_show_policy_json(monkeypatch, capsys, tmp_path: Path) -> None:
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod

    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "next_actions_for_reason",
        lambda _reason: [],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--show-policy",
            "--json",
        ],
    )
    exit_code = cli_ocr_test.main()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["policy_enabled_base"] is True
    assert payload["policy_enabled_effective"] is True
    assert payload["sandbox_db_path"] is None


def test_cli_sandbox_keep_artifacts_includes_path(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod

    base_db = tmp_path / "base.sqlite3"
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    sandbox_db = sandbox_dir / "core.sqlite3"
    sqlite3.connect(str(base_db)).close()
    sqlite3.connect(str(sandbox_db)).close()

    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        sandbox_mod,
        "create_sandbox_copy",
        lambda _tenant: (sandbox_db, sandbox_dir),
    )
    monkeypatch.setattr(sandbox_mod, "cleanup_sandbox", lambda _sandbox_dir: None)

    def _policy_status(_tenant_id: str, *, db_path: Path) -> dict[str, object]:
        if db_path == base_db:
            return {
                "ok": True,
                "policy_enabled": False,
                "ocr_column": "allow_ocr",
                "row_present": True,
                "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
                "table": "knowledge_source_policies",
            }
        return {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        }

    monkeypatch.setattr(policy_mod, "get_policy_status", _policy_status)
    monkeypatch.setattr(
        ocr_test,
        "run_ocr_test",
        lambda *_args, **_kwargs: {
            "ok": True,
            "reason": None,
            "tenant_id": "dev",
            "sandbox": False,
            "policy_enabled": True,
            "policy_enabled_base": None,
            "policy_enabled_effective": None,
            "policy_reason": None,
            "existing_columns": None,
            "tesseract_found": True,
            "read_only": False,
            "job_status": "done",
            "job_error_code": None,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "duration_ms": 1,
            "chars_out": 1,
            "truncated": False,
            "sandbox_db_path": None,
            "next_actions": [],
            "message": "ok",
        },
    )
    monkeypatch.setattr(ocr_test, "detect_read_only", lambda: False)
    monkeypatch.setattr(ocr_test, "next_actions_for_reason", lambda _reason: [])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--json",
            "--keep-artifacts",
        ],
    )
    exit_code = cli_ocr_test.main()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert exit_code == 0
    assert payload["policy_enabled_base"] is False
    assert payload["policy_enabled_effective"] is True
    assert payload["sandbox_db_path"] == "<path>"


def test_cli_enable_policy_in_sandbox_read_only_refused(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod

    base_db = tmp_path / "base.sqlite3"
    sandbox_dir = tmp_path / "sandbox-ro"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    sandbox_db = sandbox_dir / "core.sqlite3"
    sqlite3.connect(str(base_db)).close()
    sqlite3.connect(str(sandbox_db)).close()

    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        sandbox_mod,
        "create_sandbox_copy",
        lambda _tenant: (sandbox_db, sandbox_dir),
    )
    monkeypatch.setattr(sandbox_mod, "cleanup_sandbox", lambda _sandbox_dir: None)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": False,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        policy_mod,
        "enable_ocr_policy_in_db",
        lambda *_args, **_kwargs: {
            "ok": False,
            "reason": "read_only",
        },
    )
    monkeypatch.setattr(
        ocr_test,
        "run_ocr_test",
        lambda *_args, **_kwargs: {
            "ok": False,
            "reason": "read_only",
            "tenant_id": "dev",
            "sandbox": True,
            "policy_enabled": False,
            "policy_enabled_base": None,
            "policy_enabled_effective": None,
            "policy_reason": None,
            "existing_columns": None,
            "tesseract_found": True,
            "read_only": True,
            "job_status": None,
            "job_error_code": None,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "duration_ms": None,
            "chars_out": None,
            "truncated": False,
            "sandbox_db_path": None,
            "next_actions": [],
            "message": "READ_ONLY active; skipping ingest/job run.",
        },
    )
    monkeypatch.setattr(ocr_test, "detect_read_only", lambda: True)
    monkeypatch.setattr(
        ocr_test,
        "next_actions_for_reason",
        lambda reason: (
            ["Disable READ_ONLY for dev testing."] if reason == "read_only" else []
        ),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--json",
            "--enable-policy-in-sandbox",
        ],
    )
    exit_code = cli_ocr_test.main()
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert exit_code == 1
    assert payload["reason"] == "read_only"
    assert payload["ok"] is False


def test_cli_passes_seed_and_direct_submit_flags(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod

    base_db = tmp_path / "base.sqlite3"
    sandbox_dir = tmp_path / "sandbox-flags"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    sandbox_db = sandbox_dir / "core.sqlite3"
    sqlite3.connect(str(base_db)).close()
    sqlite3.connect(str(sandbox_db)).close()

    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        sandbox_mod,
        "create_sandbox_copy",
        lambda _tenant: (sandbox_db, sandbox_dir),
    )
    monkeypatch.setattr(sandbox_mod, "cleanup_sandbox", lambda _sandbox_dir: None)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    captured: dict[str, object] = {}

    def _run(*_args, **kwargs):
        captured["seed_watch_config_in_sandbox"] = kwargs.get(
            "seed_watch_config_in_sandbox"
        )
        captured["direct_submit_in_sandbox"] = kwargs.get("direct_submit_in_sandbox")
        return {
            "ok": True,
            "reason": None,
            "tenant_id": "dev",
            "sandbox": True,
            "policy_enabled": True,
            "policy_enabled_base": None,
            "policy_enabled_effective": None,
            "policy_reason": None,
            "existing_columns": None,
            "tesseract_found": True,
            "read_only": False,
            "job_status": "done",
            "job_error_code": None,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "duration_ms": 1,
            "chars_out": 1,
            "truncated": False,
            "sandbox_db_path": None,
            "watch_config_seeded": False,
            "watch_config_existed": None,
            "inbox_dir_used": "/tmp/inbox",
            "scanner_discovered_files": 1,
            "direct_submit_used": False,
            "source_lookup_reason": None,
            "source_files_columns": None,
            "next_actions": [],
            "message": "ok",
        }

    monkeypatch.setattr(ocr_test, "run_ocr_test", _run)
    monkeypatch.setattr(ocr_test, "detect_read_only", lambda: False)
    monkeypatch.setattr(ocr_test, "next_actions_for_reason", lambda _reason: [])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--json",
            "--no-seed-watch-config-in-sandbox",
            "--direct-submit-in-sandbox",
        ],
    )
    exit_code = cli_ocr_test.main()
    _ = capsys.readouterr().out.strip()
    assert exit_code == 0
    assert captured["seed_watch_config_in_sandbox"] is False
    assert captured["direct_submit_in_sandbox"] is True


def test_cli_show_tesseract_json(monkeypatch, capsys, tmp_path: Path) -> None:
    import app.autonomy.ocr as ocr_mod
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod
    import app.devtools.tesseract_probe as probe_mod

    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        ocr_mod, "resolve_tesseract_bin", lambda: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": None,
            "bin_path": "/usr/bin/tesseract",
            "tessdata_dir": "/opt/homebrew/share/tessdata",
            "tessdata_source": "heuristic",
            "langs": ["eng", "deu"],
            "lang_used": "eng",
            "stderr_tail": None,
            "next_actions": [],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli_ocr_test", "--tenant", "dev", "--show-tesseract", "--json"],
    )
    exit_code = cli_ocr_test.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["tesseract_found"] is True
    assert payload["tessdata_dir"] == "<path>"


def test_cli_show_tesseract_ok_with_warnings_exit_2(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.autonomy.ocr as ocr_mod
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod
    import app.devtools.tesseract_probe as probe_mod

    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        ocr_mod, "resolve_tesseract_bin", lambda: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok_with_warnings",
            "bin_path": "/usr/bin/tesseract",
            "tessdata_prefix": "/usr/share",
            "tessdata_dir_used": "/usr/share",
            "tessdata_source": "heuristic",
            "langs": ["deu", "osd"],
            "lang_selected": "deu",
            "warnings": ["Error opening data file <path>/eng.traineddata"],
            "stderr_tail": "Error opening data file <path>/eng.traineddata",
            "next_actions": ["Install eng traineddata (recommended)."],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli_ocr_test", "--tenant", "dev", "--show-tesseract", "--json"],
    )
    exit_code = cli_ocr_test.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert payload["ok"] is True
    assert payload["reason"] == "ok_with_warnings"


def test_cli_show_tesseract_ok_with_warnings_strict_exit_1(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.autonomy.ocr as ocr_mod
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod
    import app.devtools.tesseract_probe as probe_mod

    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        ocr_mod, "resolve_tesseract_bin", lambda: Path("/usr/bin/tesseract")
    )
    monkeypatch.setattr(
        probe_mod,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok_with_warnings",
            "bin_path": "/usr/bin/tesseract",
            "tessdata_prefix": "/usr/share",
            "tessdata_dir_used": "/usr/share",
            "tessdata_source": "heuristic",
            "langs": ["deu", "osd"],
            "lang_selected": "deu",
            "warnings": ["Error opening data file <path>/eng.traineddata"],
            "stderr_tail": "Error opening data file <path>/eng.traineddata",
            "next_actions": ["Install eng traineddata (recommended)."],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--show-tesseract",
            "--strict",
            "--json",
        ],
    )
    exit_code = cli_ocr_test.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["reason"] == "tesseract_warning"


def test_cli_doctor_write_support_bundle_keeps_exit_contract(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.devtools.ocr_doctor as doctor_mod
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod
    import app.devtools.support_bundle as bundle_mod

    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        doctor_mod,
        "run_ocr_doctor",
        lambda *args, **kwargs: (
            {
                "ok": True,
                "reason": "ok_with_warnings",
                "tenant_id": "dev",
                "smoke": {"ok": True, "reason": None},
                "next_actions": [],
            },
            2,
        ),
    )

    captured: dict[str, object] = {}

    def _bundle(*args, **kwargs):
        captured["sandbox_e2e_result"] = kwargs.get("sandbox_e2e_result")
        return {
            "ok": True,
            "bundle_dir": "docs/devtools/support_bundles/x",
            "zip_path": "docs/devtools/support_bundles/x/support_bundle.zip",
            "files": ["ocr_doctor.json", "schema_snapshot.json"],
            "reason": None,
        }

    monkeypatch.setattr(bundle_mod, "write_support_bundle", _bundle)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--doctor",
            "--doctor-only",
            "--write-support-bundle",
            "--json",
        ],
    )
    exit_code = cli_ocr_test.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert payload["reason"] == "ok_with_warnings"
    assert payload["support_bundle"]["ok"] is True
    assert captured["sandbox_e2e_result"] is None


def test_cli_doctor_support_bundle_failure_forces_error(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.devtools.ocr_doctor as doctor_mod
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod
    import app.devtools.support_bundle as bundle_mod

    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: {
            "ok": True,
            "policy_enabled": True,
            "ocr_column": "allow_ocr",
            "row_present": True,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "table": "knowledge_source_policies",
        },
    )
    monkeypatch.setattr(
        doctor_mod,
        "run_ocr_doctor",
        lambda *args, **kwargs: (
            {
                "ok": True,
                "reason": None,
                "tenant_id": "dev",
                "smoke": {"ok": True, "reason": None},
                "next_actions": [],
            },
            0,
        ),
    )
    monkeypatch.setattr(
        bundle_mod,
        "write_support_bundle",
        lambda *args, **kwargs: {
            "ok": False,
            "bundle_dir": "docs/devtools/support_bundles/x",
            "zip_path": None,
            "files": [],
            "reason": "permission_denied",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--doctor",
            "--write-support-bundle",
            "--json",
        ],
    )
    exit_code = cli_ocr_test.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 1
    assert payload["reason"] == "support_bundle_failed"
    assert payload["support_bundle"]["ok"] is False
