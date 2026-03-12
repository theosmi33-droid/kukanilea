# Pipeline Reproducibility Checklist (KUKANILEA)

Dieses Dokument ergänzt `docs/dev/BOOTSTRAP_QUICKSTART.md` mit einem klaren, wiederholbaren Ablauf für lokale Reproduzierbarkeit in unter 10 Minuten.

## Ziel

- Gleiches Ergebnis auf neuem Laptop, CI-Runner und bestehender Dev-Maschine.
- Schnelle Fehlerlokalisierung bei "läuft lokal, aber nicht in CI".
- Nachweisbare Ausführung über wenige, standardisierte Kommandos.

## Preconditions

1. Git installiert und `origin` gesetzt.
2. Python-Interpreter laut `.python-version` verfügbar.
3. Netzwerkzugang für initiale Dependency-Installation.
4. Schreibrechte auf Projektordner.

## Standardablauf

1. **Clone + bootstrap**
   - `bash scripts/dev_bootstrap.sh`
2. **Dev-Start**
   - `bash scripts/dev_run.sh`
3. **Healthcheck**
   - `./scripts/ops/healthcheck.sh`
4. **Evidence Gate**
   - `scripts/ops/launch_evidence_gate.sh`

## Fast Path

Wenn nur ein kurzer Funktionscheck nötig ist:

- `bash scripts/dev_bootstrap.sh --fast`
- `./scripts/ops/healthcheck.sh`

## Troubleshooting-Matrix

| Symptom | Wahrscheinliche Ursache | Konkreter Fix |
|---|---|---|
| `pytest not found` | Falscher pyenv Interpreter | `PYENV_VERSION=3.12.0 pytest -q ...` |
| `Playwright browser missing` | Browser nicht installiert | `playwright install chromium` |
| Healthcheck rot bei DB | fehlende Migration/lock | `python run.py migrate && retry` |
| Evidence Gate FAIL | fehlende Pflichtartefakte | Healthcheck + Security Gate erneut ausführen |
| `gh` liefert auth Fehler | Token/Account nicht aktiv | `gh auth status` + re-login |

## Repro Contract (Do/Don't)

### Do

- Nutze `rg -n` für zielgerichtete Dateisuche.
- Nutze fokussierte `pytest`-Läufe für betroffene Domänen.
- Halte PR-Diffs klein und lane-fokussiert.
- Hänge Testevidenz in die PR-Beschreibung.

### Don't

- Keine globalen Full-Suite-Läufe bei reinen Doku-PRs.
- Keine destruktiven Git-Kommandos (`reset --hard`, force-push).
- Keine stillen Policy-Änderungen ohne Dokumentation.

## Minimal Evidence Pack

Jeder Repro-Check sollte mindestens enthalten:

1. Bootstrap-Kommando + Exitcode.
2. Healthcheck-Ausgabe (PASS/FAIL).
3. Relevante `pytest`-Ausgabe.
4. Optional: Security Gate Ergebnis.

## CI-Abgleich

Lokale Verifikation ist dann "CI-nah", wenn folgende Signale lokal ebenfalls grün sind:

- `lint-and-scan`
- `pr-quality-guard`
- `test` (oder betroffene Teilmenge bei Doku-only PR)
- bei CI-Laufzeitoptimierungen: ausgelagerte Suites weiter über `quality-gates` absichern (`tests/contracts`, `tests/integration/test_end_to_end_core_smoke.py`)
- `policy-baseline-validate` bei Änderungen an `.github/policy/branch_protection_baseline.json`

## Day-2 Routine

- Täglich vor Arbeitsstart: `gh pr status` + `git pull --ff-only`.
- Vor jedem Push: ein lokaler Smokecheck.
- Bei roten Checks: zuerst Log analysieren, dann minimaler Fix.
- Bei roten GitHub-Action-Runs: nur actionable Failures prüfen
  (`main` + offene PR-Branches), keine historische Branch-Historie jagen.

## Copy/Paste Command Bundle

```bash
# bootstrap + run
bash scripts/dev_bootstrap.sh --fast
bash scripts/dev_run.sh

# quality checks
bash scripts/dev/pr_quality_guard.sh --ci
./scripts/ops/healthcheck.sh
scripts/ops/launch_evidence_gate.sh
scripts/ops/list_actionable_failures.sh

# targeted tests examples
PYENV_VERSION=3.12.0 pytest -q tests/test_tool_interface.py
PYENV_VERSION=3.12.0 pytest -q tests/contracts/test_tool_contract_endpoints_presence.py
```

## Success Criteria

Ein Repro-Lauf gilt als erfolgreich, wenn:

1. Bootstrap ohne manuelle Nacharbeit durchläuft.
2. Dev-Server startbar ist.
3. Healthcheck grün ist.
4. Mindestens ein zielgerichteter Testlauf grün ist.

## Ownership

- Primär verantwortlich: `dev-ci` Lane.
- Mitverantwortlich: `ops-release` für Evidence- und Health-Gates.

## Änderungsregel

Bei Änderungen an `scripts/dev_bootstrap.sh`, `scripts/dev_run.sh`, `scripts/ops/healthcheck.sh` oder `scripts/ops/launch_evidence_gate.sh` muss dieses Dokument geprüft und bei Bedarf aktualisiert werden.
