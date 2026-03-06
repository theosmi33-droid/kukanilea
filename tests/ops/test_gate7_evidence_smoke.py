from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ops.gate7_evidence import evaluate_gate7


SCRIPT = Path("scripts/ops/gate7_evidence.py")


def test_gate7_smoke_evaluate_reports_all_required_checks() -> None:
    payload = evaluate_gate7()

    assert payload["overall_status"] == "PASS"
    names = {entry["name"] for entry in payload["checks"]}
    assert names == {
        "lokales_modell_aktiv",
        "summary_read_api_ok",
        "write_confirm_gate_erzwungen",
        "write_mit_confirm_moeglich",
        "audit_logs_vorhanden",
        "injection_blockiert",
    }
    assert all(entry["passed"] for entry in payload["checks"])


def test_gate7_smoke_matrix_contains_router_approval_audit_guardrail_paths() -> None:
    payload = evaluate_gate7()
    matrix = payload["matrix"]

    assert matrix["summary_read_api_ok"]["action"] == "dashboard.summary.read"
    assert matrix["summary_read_api_ok"]["execution_mode"] == "read"
    assert matrix["write_confirm_gate_erzwungen"]["status"] == "confirm_required"
    assert matrix["write_confirm_gate_erzwungen"]["reason"] == "approval_required"
    assert matrix["write_mit_confirm_moeglich"]["status"] == "routed"
    assert matrix["injection_blockiert"]["status"] == "blocked"
    assert matrix["injection_blockiert"]["reason"] == "prompt_injection"


def test_gate7_smoke_cli_writes_repo_evidence_artifacts(tmp_path: Path) -> None:
    out_dir = tmp_path / "evidence"

    run = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(out_dir)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert run.returncode == 0, run.stderr
    payload = json.loads((out_dir / "gate7_smoke.json").read_text(encoding="utf-8"))
    assert payload["overall_status"] == "PASS"
    markdown = (out_dir / "gate7_smoke.md").read_text(encoding="utf-8")
    assert "# Gate 7 Smoke Evidence" in markdown
    assert "| Check | Result | Detail |" in markdown
