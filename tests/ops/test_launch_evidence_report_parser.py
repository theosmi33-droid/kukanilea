import importlib.util
import json
from pathlib import Path


def _load_parser_module():
    module_path = Path("scripts/ops/launch_evidence_report_parser.py")
    spec = importlib.util.spec_from_file_location("launch_evidence_report_parser", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_expected_exit_code_go():
    parser = _load_parser_module()
    assert parser.expected_exit_code({"counts": {"warn": 0, "fail": 0}}) == 0


def test_expected_exit_code_warn():
    parser = _load_parser_module()
    assert parser.expected_exit_code({"counts": {"warn": 1, "fail": 0}}) == 2


def test_expected_exit_code_no_go():
    parser = _load_parser_module()
    assert parser.expected_exit_code({"counts": {"warn": 0, "fail": 1}}) == 3


def test_is_valid_report_true_for_complete_payload():
    parser = _load_parser_module()
    payload = {
        "timestamp": "2026-03-05T00:00:00Z",
        "decision": "PASS",
        "exit_code": 0,
        "counts": {"pass": 3, "warn": 0, "fail": 0},
        "gates": [{"name": "Repo/CI", "status": "PASS", "note": "ok"}],
    }
    assert parser.is_valid_report(payload)


def test_load_report_reads_json(tmp_path: Path):
    parser = _load_parser_module()
    report_path = tmp_path / "report.json"
    payload = {
        "timestamp": "2026-03-05T00:00:00Z",
        "decision": "WARN",
        "exit_code": 2,
        "counts": {"pass": 1, "warn": 1, "fail": 0},
        "gates": [],
    }
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    assert parser.load_report(report_path)["decision"] == "WARN"


def test_gate7_artifact_path_contract_is_env_resolved() -> None:
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "GATE7_OUTPUT_DIR=\\\"$GATE7_OUTPUT_DIR\\\"" in script
    assert "base = Path(os.environ['GATE7_OUTPUT_DIR'])" in script
