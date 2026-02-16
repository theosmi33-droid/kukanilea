from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import app.devtools.cli_ocr_test as cli_ocr_test
import app.devtools.ocr_doctor as ocr_doctor


def _policy_ok(enabled: bool = True) -> dict[str, object]:
    return {
        "ok": True,
        "policy_enabled": enabled,
        "ocr_column": "allow_ocr",
        "row_present": True,
        "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
        "table": "knowledge_source_policies",
    }


def test_run_ocr_doctor_schema_and_exit_ok(monkeypatch, tmp_path: Path) -> None:
    base_db = tmp_path / "base.sqlite3"
    sandbox_dir = tmp_path / "sandbox"
    sandbox_db = sandbox_dir / "core.sqlite3"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(base_db)).close()
    sqlite3.connect(str(sandbox_db)).close()

    monkeypatch.setattr(ocr_doctor, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        ocr_doctor,
        "get_policy_status",
        lambda _tenant, *, db_path: _policy_ok(db_path == sandbox_db),
    )
    monkeypatch.setattr(ocr_doctor, "detect_read_only", lambda: False)
    monkeypatch.setattr(
        ocr_doctor,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok",
            "tesseract_found": True,
            "bin_path": "/usr/bin/tesseract",
            "tesseract_bin_used": "/usr/bin/tesseract",
            "tesseract_version": "tesseract 5.5.2",
            "supports_print_tessdata_dir": True,
            "print_tessdata_dir": "/usr/share/tessdata",
            "tessdata_prefix": "/usr/share",
            "tessdata_candidates": ["/usr/share"],
            "langs": ["eng", "deu"],
            "lang_selected": "eng",
            "warnings": [],
            "stderr_tail": None,
            "next_actions": [],
        },
    )
    monkeypatch.setattr(
        ocr_doctor,
        "create_sandbox_copy",
        lambda _tenant: (sandbox_db, sandbox_dir),
    )
    monkeypatch.setattr(ocr_doctor, "cleanup_sandbox", lambda _sandbox_dir: None)
    monkeypatch.setattr(
        ocr_doctor,
        "enable_ocr_policy_in_db",
        lambda *_args, **_kwargs: {"ok": True, "changed": True},
    )
    monkeypatch.setattr(
        ocr_doctor,
        "run_ocr_test",
        lambda *_args, **_kwargs: {
            "ok": True,
            "reason": None,
            "policy_enabled_base": None,
            "policy_enabled_effective": True,
            "policy_reason": None,
            "existing_columns": ["tenant_id", "allow_ocr", "updated_at"],
            "job_status": "done",
            "job_error_code": None,
            "watch_config_seeded": True,
            "watch_config_existed": False,
            "inbox_dir_used": "/tmp/inbox",
            "scanner_discovered_files": 1,
            "direct_submit_used": True,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "next_actions": [],
            "message": "ok",
        },
    )

    report, exit_code = ocr_doctor.run_ocr_doctor(
        "dev",
        json_mode=True,
        strict=False,
        timeout_s=15,
    )
    assert exit_code == 0
    assert report["ok"] is True
    assert report["tenant_id"] == "dev"
    assert "environment" in report
    assert "smoke" in report
    assert report["job_status"] == "done"
    assert "pilot+test@example.com" not in json.dumps(report, sort_keys=True)


def test_run_ocr_doctor_warning_exit_mapping(monkeypatch, tmp_path: Path) -> None:
    base_db = tmp_path / "base.sqlite3"
    sandbox_dir = tmp_path / "sandbox"
    sandbox_db = sandbox_dir / "core.sqlite3"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(base_db)).close()
    sqlite3.connect(str(sandbox_db)).close()

    monkeypatch.setattr(ocr_doctor, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        ocr_doctor,
        "get_policy_status",
        lambda _tenant, *, db_path: _policy_ok(db_path == sandbox_db),
    )
    monkeypatch.setattr(ocr_doctor, "detect_read_only", lambda: False)
    monkeypatch.setattr(
        ocr_doctor,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok_with_warnings",
            "tesseract_found": True,
            "bin_path": "/usr/bin/tesseract",
            "tessdata_prefix": "/usr/share",
            "langs": ["deu", "osd"],
            "lang_selected": "deu",
            "warnings": ["Error opening data file <path>/eng.traineddata"],
            "stderr_tail": "Error opening data file <path>/eng.traineddata",
            "next_actions": ["Install eng traineddata (recommended)."],
        },
    )
    monkeypatch.setattr(
        ocr_doctor,
        "create_sandbox_copy",
        lambda _tenant: (sandbox_db, sandbox_dir),
    )
    monkeypatch.setattr(ocr_doctor, "cleanup_sandbox", lambda _sandbox_dir: None)
    monkeypatch.setattr(
        ocr_doctor,
        "enable_ocr_policy_in_db",
        lambda *_args, **_kwargs: {"ok": True, "changed": True},
    )
    monkeypatch.setattr(
        ocr_doctor,
        "run_ocr_test",
        lambda *_args, **_kwargs: {
            "ok": True,
            "reason": None,
            "job_status": "done",
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "next_actions": [],
            "message": "ok",
        },
    )

    report, exit_code = ocr_doctor.run_ocr_doctor(
        "dev",
        json_mode=True,
        strict=False,
        timeout_s=15,
    )
    assert report["ok"] is True
    assert report["reason"] == "ok_with_warnings"
    assert exit_code == 2

    strict_report, strict_exit = ocr_doctor.run_ocr_doctor(
        "dev",
        json_mode=True,
        strict=True,
        timeout_s=15,
    )
    assert strict_report["ok"] is False
    assert strict_report["reason"] == "tesseract_warning"
    assert strict_exit == 1


def test_run_ocr_doctor_commit_guard(monkeypatch, tmp_path: Path) -> None:
    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(ocr_doctor, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        ocr_doctor, "get_policy_status", lambda _tenant, *, db_path: _policy_ok(False)
    )
    monkeypatch.setattr(ocr_doctor, "detect_read_only", lambda: False)
    monkeypatch.setattr(
        ocr_doctor,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": True,
            "reason": "ok",
            "tesseract_found": True,
            "bin_path": "/usr/bin/tesseract",
            "langs": ["eng"],
            "lang_selected": "eng",
            "warnings": [],
            "stderr_tail": None,
            "next_actions": [],
        },
    )
    monkeypatch.setattr(
        ocr_doctor,
        "run_ocr_test",
        lambda *_args, **_kwargs: {
            "ok": True,
            "reason": None,
            "job_status": "done",
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "next_actions": [],
            "message": "ok",
        },
    )

    called = {"n": 0}

    def _enable(*_args, **_kwargs):
        called["n"] += 1
        return {"ok": True, "changed": True}

    monkeypatch.setattr(ocr_doctor, "enable_ocr_policy_in_db", _enable)
    report, exit_code = ocr_doctor.run_ocr_doctor(
        "dev",
        json_mode=True,
        strict=False,
        timeout_s=15,
        sandbox=False,
        commit_real_policy=True,
        yes_really_commit="other",
    )
    assert report["reason"] == "commit_guard_failed"
    assert report["commit_real_policy_applied"] is False
    assert exit_code == 1
    assert called["n"] == 0


def test_run_ocr_doctor_commit_blocked_in_read_only(
    monkeypatch, tmp_path: Path
) -> None:
    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(ocr_doctor, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        ocr_doctor, "get_policy_status", lambda _tenant, *, db_path: _policy_ok(False)
    )
    monkeypatch.setattr(ocr_doctor, "detect_read_only", lambda: True)
    monkeypatch.setattr(
        ocr_doctor,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": False,
            "reason": "read_only",
            "tesseract_found": False,
            "bin_path": None,
            "langs": [],
            "warnings": [],
            "stderr_tail": None,
            "next_actions": [],
        },
    )
    monkeypatch.setattr(
        ocr_doctor,
        "run_ocr_test",
        lambda *_args, **_kwargs: {
            "ok": False,
            "reason": "read_only",
            "job_status": None,
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "next_actions": [],
            "message": "read only",
        },
    )
    monkeypatch.setattr(
        ocr_doctor,
        "enable_ocr_policy_in_db",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no commit")),
    )

    report, exit_code = ocr_doctor.run_ocr_doctor(
        "dev",
        json_mode=True,
        strict=False,
        timeout_s=15,
        sandbox=False,
        commit_real_policy=True,
        yes_really_commit="dev",
    )
    assert report["reason"] == "read_only"
    assert report["commit_real_policy_applied"] is False
    assert exit_code == 1


def test_cli_doctor_writes_reports(monkeypatch, capsys, tmp_path: Path) -> None:
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod

    base_db = tmp_path / "base.sqlite3"
    report_json = tmp_path / "doctor.json"
    report_text = tmp_path / "doctor.txt"
    sqlite3.connect(str(base_db)).close()
    monkeypatch.setattr(sandbox_mod, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        policy_mod,
        "get_policy_status",
        lambda _tenant_id, *, db_path: _policy_ok(True),
    )

    monkeypatch.setattr(
        ocr_doctor,
        "run_ocr_doctor",
        lambda *args, **kwargs: (
            {
                "ok": True,
                "reason": "ok_with_warnings",
                "tenant_id": "dev",
                "strict_mode": False,
                "sandbox": True,
                "next_actions": ["check warnings"],
                "message": "warn",
            },
            2,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_ocr_test",
            "--tenant",
            "dev",
            "--doctor",
            "--json",
            "--report-json-path",
            str(report_json),
            "--report-text-path",
            str(report_text),
        ],
    )
    exit_code = cli_ocr_test.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 2
    assert payload["reason"] == "ok_with_warnings"
    assert report_json.exists()
    assert report_text.exists()
    assert json.loads(report_json.read_text(encoding="utf-8"))["tenant_id"] == "dev"
    text = report_text.read_text(encoding="utf-8")
    assert "OCR Doctor Report" in text
    assert "{" not in text
