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


def test_launch_evidence_decision_rule_is_explicit():
    script = Path("scripts/ops/launch_evidence_gate.sh").read_text(encoding="utf-8")
    assert "FAIL>0 => NO-GO, WARN>0 => WARN, else GO" in script
