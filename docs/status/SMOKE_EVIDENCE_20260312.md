# Smoke & Evidence Run (2026-03-12)

## Scope
- Finaler Smoke-/Evidence-Lauf für Kernseiten und Kernflows.
- Keine Feature-Änderungen.

## Faktenstand
- `python scripts/ops/verify_guardrails.py`: PASS.
- `bash scripts/ops/healthcheck.sh --skip-pytest`: PASS.
- `python -m pytest -q tests/ops/test_gate7_evidence_smoke.py tests/ops/test_gate7_launch_evidence_contract.py`: PASS (6 Tests).
- `bash scripts/ops/launch_evidence_gate.sh --skip-healthcheck`: Exit-Code `3` (NO-GO/FAIL).

## Kern-Evidence
- Launch-Gate Report aktualisiert:
  - `docs/reviews/codex/LAUNCH_GATE_AUTOMATION_REPORT_20260305.md`
  - `docs/reviews/codex/LAUNCH_GATE_AUTOMATION_REPORT_20260305.json`
- Gate-7-Artefakte aktualisiert:
  - `evidence/operations/gate7_latest/gate7_smoke.md`
  - `evidence/operations/gate7_latest/gate7_smoke.json`

## Beobachtete NO-GO-Fakten aus Launch-Gate
- `MIN_SCOPE`: FAIL (`files=7`, `loc=140`).
- `License`: FAIL (`LOCK:MISSING`).
- `MIA_UNCONTROLLED_WRITES`: FAIL.
- `Health`: WARN (durch Flag übersprungen).
- `E2E_Runtime`: WARN (`playwright.sync_api` nicht verfügbar).
