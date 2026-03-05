# DEV_CI Lane Report — 2026-03-05

## Preflight
1. `gh pr list --repo theosmi33-droid/kukanilea --limit 100`
   - Ergebnis: **nicht ausführbar** (`gh: command not found`) in der aktuellen Umgebung.
2. Dateioverlap geprüft über lokale Matrix:
   - `bash scripts/orchestration/overlap_matrix_11.sh`
   - Ergebnis: Lauf erfolgreich, kein lokaler Blocker im bearbeiteten DEV_CI-Allowlist-Scope.

## Umgesetzte DEV_CI-Maßnahmen

### 1) Bootstrap für frische Umgebungen robuster
- `.python-version` wird jetzt für `pyenv` gezielt berücksichtigt, sofern die Version installiert ist.
- Playwright-Installation wird klar protokolliert und in CI ohne `--with-deps` ausgeführt.

### 2) Healthcheck robuster gegen Interpreter-Drift
- Drift-Fehler liefert nun eine konkrete Re-Run-Anweisung mit `.venv/bin/python`.

### 3) CI-Required-Contexts deterministischer
- `playwright-e2e.yml` und `windows-installer.yml` erzeugen den Job-Status jetzt immer.
- Statt Job-Level-`if` wird innerhalb der Steps gegated; bei nicht erfüllter Label-Policy wird explizit erfolgreich „skipped by policy“ markiert.

### 4) Doku: reproduzierbarer Setup-/Testpfad
- README und Quickstart-Doku enthalten die exakten Pflicht-Verifikationsbefehle.
- Keine absoluten User-Pfade in der neuen/angepassten Dokumentation.

## Time-to-Green Schrittfolge
```bash
git clone <repo-url>
cd kukanilea
bash scripts/dev_bootstrap.sh
bash -n scripts/dev_bootstrap.sh scripts/dev_run.sh scripts/ops/healthcheck.sh scripts/ops/launch_evidence_gate.sh
./scripts/ops/healthcheck.sh
scripts/ops/launch_evidence_gate.sh
```
