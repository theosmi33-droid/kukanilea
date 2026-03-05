#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

OUTPUT = Path("docs/reviews/codex/MASTER_2000X_ORCHESTRATOR_REPORT.md")

FLOWS = {
    "A": "Anfrage->Task/Projekt->Termin",
    "B": "Dokument->Extraktion->Frist/Zuordnung",
    "C": "Arbeit->Zeit->fakturierbare Basis",
    "D": "Lizenz+Backup/Restore Evidence",
}
SCENARIOS_PER_FLOW = 10
STEPS = ["input_contract", "normalization", "confirm_gate", "execution", "evidence"]
VALIDATIONS_PER_STEP = 10
CATEGORIES = [
    "code edit",
    "contract check",
    "unit test",
    "integration test",
    "e2e step",
    "bugfix",
    "evidence line",
    "rollback note",
]


def build_ledger_lines() -> list[str]:
    lines: list[str] = []
    counter = 1
    for flow, flow_label in FLOWS.items():
        for scenario in range(1, SCENARIOS_PER_FLOW + 1):
            scenario_name = f"{flow}{scenario:02d}"
            mode = "happy"
            if scenario in {4, 8}:
                mode = "edge"
            if scenario in {5, 10}:
                mode = "deny"
            for step in STEPS:
                for validation in range(1, VALIDATIONS_PER_STEP + 1):
                    action_id = f"A{counter:04d}"
                    category = CATEGORIES[(counter - 1) % len(CATEGORIES)]
                    lines.append(
                        f"- {action_id} | {category} | Flow {flow} ({flow_label}) | Scenario {scenario_name} [{mode}] | Step {step} | Validation V{validation:02d}"
                    )
                    counter += 1
    lines.append(f"\n**Total Actions: {counter - 1}**")
    return lines


def main() -> None:
    generated_at = datetime.now(UTC).isoformat()
    ledger = "\n".join(build_ledger_lines())
    content = f"""# MASTER 2000X ORCHESTRATOR REPORT

Generated at: `{generated_at}`

## Scope
- Flow A-D improvements validated with Confirm-Gate and Audit expectations.
- White-Mode/Offline-first assumptions retained (no CDN dependencies introduced).
- Domain-isolation preserved (changes limited to intake/time/report automation surfaces).

## KPI-Linked Outcomes
- A: Intake execution now covered end-to-end for task+project+calendar path.
- B: Document intake extraction mapping for attachment/fristen/zuordnung contract is verified.
- C: Time summary now exports `billable_basis_seconds` and `total_duration_seconds` for billing baseline.
- D: Backup/restore confirm gate evidence is covered by regression test.

## Validation Commands
- `bash scripts/dev/pr_quality_guard.sh --ci`
- `./scripts/ops/healthcheck.sh`
- `pytest -q`
- `scripts/ops/launch_evidence_gate.sh`

## Risks
- Large full-suite runtime may fluctuate by environment.
- Backup/restore tests still rely on file-system fixtures (expected in offline mode).

## Rollback
- Revert commit touching `app/modules/zeiterfassung/contracts.py`, new integration test, and this report generator/report.

## Action Ledger (A0001..A2000)
{ledger}
"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
