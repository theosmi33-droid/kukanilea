# Launch Decision (Latest)

## Ergebnis
- **NO-GO**

## Bewertungsmatrix
- **PASS**
  - `pytest -q tests/license/test_license_state_machine.py`
  - `restore_validation.py --phase before/after` (konsistent, `ok=true`)
- **WARN**
  - Open-PR Overlap konnte ohne `gh` nur eingeschränkt verifiziert werden.
- **FAIL**
  - `./scripts/ops/healthcheck.sh` (doctor Gate)
  - `scripts/ops/launch_evidence_gate.sh` (aggregierter Gate-Fail)

## Freigabe-Kriterium für GO
GO erst wenn beide Gates grün sind:
1. `./scripts/ops/healthcheck.sh`
2. `scripts/ops/launch_evidence_gate.sh`

## Evidence Referenzen
- `evidence/operations/20260305_ops_release_evidence/pytest_license_state_machine.txt`
- `evidence/operations/20260305_ops_release_evidence/healthcheck.txt`
- `evidence/operations/20260305_ops_release_evidence/launch_evidence_gate_stdout.txt`
- `evidence/operations/20260305_ops_release_evidence/restore_validation_before.json`
- `evidence/operations/20260305_ops_release_evidence/restore_validation_after.json`
