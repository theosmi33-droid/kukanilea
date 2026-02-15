from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

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


def test_run_ocr_test_policy_denied(monkeypatch) -> None:
    monkeypatch.setattr(ocr_test, "_sandbox_context", lambda **_: _dummy_ctx())
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
