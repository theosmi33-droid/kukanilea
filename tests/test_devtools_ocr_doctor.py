from __future__ import annotations

import json
import re
import sqlite3
import sys
from hashlib import sha256
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


def _sha256_file(path: Path) -> str:
    h = sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


ABS_PATH_RE = re.compile(r"(^|[^A-Za-z0-9])/(Users|home)/")
WIN_ABS_RE = re.compile(r"[A-Za-z]:\\")


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
    assert "operator_hints" in report
    assert report["operator_hints"]["paths_sanitized"] is True
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


def test_run_ocr_doctor_hints_for_common_bootstrap_reasons(
    monkeypatch, tmp_path: Path
) -> None:
    base_db = tmp_path / "base.sqlite3"
    sqlite3.connect(str(base_db)).close()

    monkeypatch.setattr(ocr_doctor, "resolve_core_db_path", lambda: base_db)
    monkeypatch.setattr(
        ocr_doctor, "get_policy_status", lambda _tenant, *, db_path: _policy_ok(True)
    )
    monkeypatch.setattr(ocr_doctor, "detect_read_only", lambda: False)
    monkeypatch.setattr(
        ocr_doctor,
        "run_ocr_test",
        lambda *_args, **_kwargs: {
            "ok": False,
            "reason": "tessdata_missing",
            "job_status": "failed",
            "job_error_code": "tessdata_missing",
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "next_actions": [],
            "message": "missing tessdata",
        },
    )

    monkeypatch.setattr(
        ocr_doctor,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": False,
            "reason": "tessdata_missing",
            "tesseract_found": True,
            "bin_path": "/usr/bin/tesseract",
            "supports_print_tessdata_dir": True,
            "langs": [],
            "warnings": [],
            "stderr_tail": None,
            "next_actions": [],
        },
    )
    report, exit_code = ocr_doctor.run_ocr_doctor(
        "dev",
        json_mode=True,
        strict=False,
        timeout_s=10,
        sandbox=False,
    )
    assert exit_code == 1
    assert report["reason"] == "tessdata_missing"
    assert report["install_hints"] == []
    assert report["config_hints"]
    assert any("--tessdata-dir" in hint for hint in report["config_hints"])
    assert report["operator_hints"]["install_hints"] == []
    assert report["operator_hints"]["config_hints"]

    monkeypatch.setattr(
        ocr_doctor,
        "probe_tesseract",
        lambda **_kwargs: {
            "ok": False,
            "reason": "tesseract_missing",
            "tesseract_found": False,
            "bin_path": None,
            "supports_print_tessdata_dir": False,
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
            "reason": "tesseract_missing",
            "job_status": "failed",
            "job_error_code": "tesseract_missing",
            "pii_found_knowledge": False,
            "pii_found_eventlog": False,
            "next_actions": [],
            "message": "missing tesseract",
        },
    )
    report_missing, exit_missing = ocr_doctor.run_ocr_doctor(
        "dev",
        json_mode=True,
        strict=False,
        timeout_s=10,
        sandbox=False,
    )
    assert exit_missing == 1
    assert report_missing["reason"] == "tesseract_missing"
    assert report_missing["install_hints"]
    assert report_missing["config_hints"]
    serialized = json.dumps(report_missing, sort_keys=True)
    assert ABS_PATH_RE.search(serialized) is None
    assert WIN_ABS_RE.search(serialized) is None


def test_cli_doctor_write_proof_bundle_sanitized(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    import app.devtools.ocr_policy as policy_mod
    import app.devtools.sandbox as sandbox_mod

    base_db = tmp_path / "base.sqlite3"
    proof_dir = tmp_path / "proofs"
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
                "ok": False,
                "reason": "tesseract_missing",
                "tenant_id": "dev",
                "strict_mode": False,
                "sandbox": True,
                "install_hints": ["Install tesseract"],
                "config_hints": ["Use --tesseract-bin <binary>"],
                "next_actions": ["Install tesseract and ensure PATH."],
                "message": "missing",
                "inbox_dir_used": "<path>",
                "smoke": {
                    "ok": False,
                    "reason": "tesseract_missing",
                    "inbox_dir_used": "<path>",
                    "message": "missing",
                },
            },
            1,
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
            "--write-proof",
            "--proof-dir",
            str(proof_dir),
        ],
    )
    exit_code = cli_ocr_test.main()
    payload = json.loads(capsys.readouterr().out.strip())
    assert exit_code == 1
    assert payload["reason"] == "tesseract_missing"
    doctor_proof = proof_dir / "ocr_doctor_proof.json"
    smoke_proof = proof_dir / "ocr_sandbox_e2e_proof.json"
    assert doctor_proof.exists()
    assert smoke_proof.exists()
    doctor_payload = json.loads(doctor_proof.read_text())
    smoke_payload = json.loads(smoke_proof.read_text())
    assert doctor_payload["tenant_id"] == "dev"
    assert smoke_payload["reason"] == "tesseract_missing"
    serialized = json.dumps(doctor_payload, sort_keys=True)
    assert "pilot+test@example.com" not in serialized
    assert ABS_PATH_RE.search(serialized) is None


def test_ocr_v0_readiness_introspection_no_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "core.sqlite3"
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE knowledge_source_policies(tenant_id TEXT PRIMARY KEY, allow_ocr INTEGER)"
        )
        con.execute(
            "CREATE TABLE source_watch_config(tenant_id TEXT PRIMARY KEY, documents_inbox_dir TEXT)"
        )
        con.execute(
            "CREATE TABLE source_files(id TEXT PRIMARY KEY, tenant_id TEXT, basename TEXT)"
        )
        con.execute(
            "CREATE TABLE autonomy_ocr_jobs(id TEXT PRIMARY KEY, tenant_id TEXT, status TEXT)"
        )
        con.commit()
    finally:
        con.close()

    before = _sha256_file(db_path)
    readiness = ocr_doctor._ocr_v0_readiness(db_path)  # noqa: SLF001
    after = _sha256_file(db_path)

    assert before == after
    assert readiness["ocr_v0_tables_present"] is True
    assert isinstance(readiness["ocr_v0_present"], bool)
    assert isinstance(readiness["ocr_v0_pipeline_callable"], bool)
