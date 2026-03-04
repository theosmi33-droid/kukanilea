from pathlib import Path

from kukanilea.devtools.platform_hardening import (
    DoctorResult,
    check_python_version,
    collect_doctor_results,
    summarize_exit_code,
    to_json_payload,
)


def test_check_python_version_success(tmp_path: Path) -> None:
    version_file = tmp_path / ".python-version"
    version_file.write_text("3.12.0\n", encoding="utf-8")

    ok, detail = check_python_version(version_file, current=(3, 12, 6))

    assert ok is True
    assert "satisfied" in detail


def test_check_python_version_failure(tmp_path: Path) -> None:
    version_file = tmp_path / ".python-version"
    version_file.write_text("3.11.8\n", encoding="utf-8")

    ok, detail = check_python_version(version_file, current=(3, 12, 1))

    assert ok is False
    assert "mismatch" in detail


def test_check_python_version_missing_file(tmp_path: Path) -> None:
    ok, detail = check_python_version(tmp_path / ".python-version")
    assert ok is False
    assert "Missing" in detail


def test_collect_doctor_results_contains_build_venv(tmp_path: Path) -> None:
    (tmp_path / ".python-version").write_text("3.12.0\n", encoding="utf-8")
    (tmp_path / ".build_venv").mkdir()

    results = collect_doctor_results(tmp_path, required_tools=("python",))

    names = {r.check for r in results}
    assert "python-version" in names
    assert "python" in names
    assert ".build_venv" in names
    build_result = next(r for r in results if r.check == ".build_venv")
    assert build_result.ok is True


def test_summarize_exit_code_reports_failure() -> None:
    results = [
        DoctorResult(check="python", ok=True, detail="ok"),
        DoctorResult(check="gh", ok=False, detail="missing"),
    ]

    assert summarize_exit_code(results) == 2


def test_to_json_payload_shape() -> None:
    payload = to_json_payload([DoctorResult(check="python", ok=True, detail="ready")])
    assert '"ok": true' in payload
    assert '"check": "python"' in payload
