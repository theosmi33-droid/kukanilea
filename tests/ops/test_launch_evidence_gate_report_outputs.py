from __future__ import annotations

import json
from pathlib import Path

SCRIPT = Path("scripts/ops/launch_evidence_gate.sh")


def _script() -> str:
    assert SCRIPT.exists()
    return SCRIPT.read_text(encoding="utf-8")


def test_launch_gate_declares_expected_exit_codes() -> None:
    text = _script()
    assert "EXIT_GO=0" in text
    assert "EXIT_WARN=2" in text
    assert "EXIT_NO_GO=3" in text


def test_launch_gate_declares_required_gate_names() -> None:
    text = _script()
    for gate in [
        "Repo/CI",
        "MIN_SCOPE",
        "Health",
        "E2E_Runtime",
        "Zero-CDN",
        "White-mode",
        "License",
        "Backup",
        "AI",
        "MIN_TESTS",
        "CI_GATE",
        "Evidence",
    ]:
        assert gate in text


def test_launch_gate_declares_playwright_runtime_note() -> None:
    text = _script()
    assert "playwright.sync_api unavailable" in text
    assert "python e2e skipped by contract" in text


def test_launch_gate_checks_backup_restore_hook_markers() -> None:
    text = _script()
    assert "backup_verify_hook=ok" in text
    assert "restore_verify_hook=ok" in text
    assert "restore_validation=ok" in text


def test_launch_gate_builds_json_report_with_gates_and_counts() -> None:
    text = _script()
    assert '"gates": gates' in text
    assert '"counts": {"pass": int(p), "warn": int(w), "fail": int(f)}' in text
    assert '"decision": decision' in text


def test_launch_gate_enforces_scope_threshold_constants() -> None:
    text = _script()
    assert "scope_files >= 8" in text
    assert "scope_loc >= 230" in text


def test_launch_gate_enforces_ops_test_count_threshold() -> None:
    text = _script()
    assert "ops_test_count" in text
    assert "need >=7" in text


def test_launch_gate_binds_gate7_artifact_dir_via_environment() -> None:
    text = _script()
    assert "GATE7_OUTPUT_DIR=\\\"$GATE7_OUTPUT_DIR\\\"" in text
    assert "base = Path(os.environ['GATE7_OUTPUT_DIR'])" in text


def test_launch_gate_decision_state_values_are_deterministic() -> None:
    text = _script()
    assert 'DECISION="PASS"' in text
    assert 'DECISION="WARN"' in text
    assert 'DECISION="FAIL"' in text


def test_actions_api_json_schema_files_parse() -> None:
    # sanity guard: keep json report serializer assumptions valid in repo
    schema_files = [
        Path("docs/contracts/actions_api/schemas/tool_action_execute.request.schema.json"),
        Path("docs/contracts/actions_api/schemas/tool_action_execute.response.schema.json"),
    ]
    for schema in schema_files:
        assert schema.exists(), f"missing {schema}"
        data = json.loads(schema.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data.get("type") == "object"
