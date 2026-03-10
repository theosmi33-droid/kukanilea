from pathlib import Path


def test_launch_evidence_uses_required_exit_codes():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "EXIT_GO=0" in script
    assert "EXIT_WARN=2" in script
    assert "EXIT_NO_GO=3" in script


def test_launch_evidence_contains_required_gate_names():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    for gate in ["Repo/CI", "Health", "Zero-CDN", "White-mode", "License", "Backup", "AI"]:
        assert gate in script


def test_launch_evidence_contains_hard_gates():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "MIN_SCOPE" in script
    assert "MIN_TESTS" in script
    assert "CI_GATE" in script
    assert "LAUNCH_GATE_AUTOMATION_REPORT_20260305.md" in script


def test_launch_evidence_json_contains_gate_matrix():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert '"gates": gates' in script
    assert '"name": names[i]' in script
    assert '"status": statuses[i]' in script


def test_launch_evidence_uses_deterministic_decision_states():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert 'DECISION="PASS"' in script
    assert 'DECISION="WARN"' in script
    assert 'DECISION="FAIL"' in script


def test_launch_evidence_requires_backup_restore_hook_evidence():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "backup_verify_hook=ok" in script
    assert "restore_verify_hook=ok" in script


def test_launch_evidence_allows_gate7_evidence_paths_for_controlled_writes():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "MIA_UNCONTROLLED_WRITES" in script
    assert "evidence/operations/" in script


def test_launch_evidence_gate7_artifacts_use_env_bound_output_dir():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "export GATE7_OUTPUT_DIR" in script
    assert "base = Path(os.environ['GATE7_OUTPUT_DIR'])" in script
