# OPS Release Lane Report — 2026-03-05

## Preflight (Open-PR overlap)
- Status: **WARN**
- Grund: `gh` CLI ist in dieser Umgebung nicht verfügbar, daher konnte kein Live-Abgleich offener PR-Dateien gegen den Scope erfolgen.
- Ersatzprüfung: Scope wurde strikt auf Allowlist-Dateien begrenzt.

## PASS/WARN/FAIL Kriterien
- **PASS**: Command exit code `0` und Output ohne Gate-Fehler.
- **WARN**: Command technisch ausführbar, aber Umgebungslimit (fehlende Tools/Remote-Metadaten).
- **FAIL**: Command liefert Non-Zero wegen fachlichem Gate-Fail.

## Pflicht-Checks (DoD-relevant)
1. License State Machine
   - Status: **PASS**
   - Evidence: `evidence/operations/20260305_ops_release_evidence/pytest_license_state_machine.txt`
2. Core Healthcheck
   - Status: **FAIL**
   - Ursache: `doctor` meldet fehlende Python-Module (`flask`, `playwright`) in Runtime.
   - Evidence: `evidence/operations/20260305_ops_release_evidence/healthcheck.txt`
3. Launch Evidence Gate
   - Status: **FAIL**
   - Ursache: propagierte Healthcheck/Pytest-Gates im Gesamt-Gate.
   - Evidence: `evidence/operations/20260305_ops_release_evidence/launch_evidence_gate_stdout.txt`

## Backup/Restore-Drill Stabilität
- Backup-/Restore-Reports besitzen jetzt `report_version=1`.
- Zeitstempel sind für Drills über Env reproduzierbar:
  - Backup: `BACKUP_TIMESTAMP`
  - Restore: `RESTORE_TIMESTAMP`
- Restore-Validation schreibt ein fixes JSON-Artefakt (`restore_validation_file`) für Nachvollziehbarkeit.

## Restore Validation (vorher/nachher)
- `before` Baseline erzeugt.
- `after` Vergleich erzeugt (`ok: true`, `issues: []`).
- Evidence:
  - `evidence/operations/20260305_ops_release_evidence/restore_validation_before.json`
  - `evidence/operations/20260305_ops_release_evidence/restore_validation_after.json`
