from pathlib import Path


SCRIPT = Path("scripts/ops/launch_evidence_gate.sh")


def test_launch_evidence_runs_gate7_smoke_harness() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "MIA_GATE7_SMOKE" in script
    assert "scripts/ops/gate7_evidence.py" in script


def test_launch_evidence_requires_gate7_artifact_matrix() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "MIA_GATE7_ARTIFACTS" in script
    assert "base = Path('$GATE7_OUTPUT_DIR')" in script
    for name in [
        "lokales_modell_aktiv",
        "summary_read_api_ok",
        "write_confirm_gate_erzwungen",
        "write_mit_confirm_moeglich",
        "audit_logs_vorhanden",
        "injection_blockiert",
    ]:
        assert name in script
