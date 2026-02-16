from __future__ import annotations

import contextlib
import json
import sqlite3
import sys
from pathlib import Path

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


def test_run_ocr_test_tesseract_missing(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
    monkeypatch.setattr(
        ocr_test, "get_policy_status", lambda *_args, **_kwargs: _policy_ok(True)
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
    assert payload["sandbox_db_path"] == str(sandbox_db)


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
    assert exit_code == 2
    assert payload["reason"] == "read_only"
    assert payload["ok"] is False
