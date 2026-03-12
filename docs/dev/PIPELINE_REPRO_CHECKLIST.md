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

_Support-Playbook (operativ, current main)_

| Symptom | Wahrscheinliche Ursache | Konkreter Fix |
|---|---|---|
| `Interpreter drift detected` im Healthcheck | Healthcheck läuft nicht mit `.venv` | `PYTHON=.venv/bin/python scripts/ops/healthcheck.sh` |
| `pytest is not installed for interpreter` / `pytest not found` | Globaler Python statt Projekt-`.venv` | `.venv` aktivieren oder `PYTHON=.venv/bin/python` setzen und Bootstrap erneut laufen lassen |
| `Optional dependency 'playwright' not available` / `Playwright browser missing` | Python-Paket `playwright` fehlt oder Browser nicht installiert | `PYTHON=.venv/bin/python scripts/dev/doctor.sh --strict` und anschließend `PYTHON=.venv/bin/python -m playwright install --with-deps chromium` |
| DB-/Seed-Fehler bei `seed_demo_data.py` oder Migration | Zielpfad nicht beschreibbar oder DB-Lock | Schreibbaren DB-Pfad verwenden (z. B. via `KUKANILEA_AUTH_DB`) und Seed/Migration erneut starten |
| Evidence Gate FAIL | Pflichtartefakte wurden im Lauf nicht erzeugt | `scripts/ops/healthcheck.sh` und danach `scripts/ops/launch_evidence_gate.sh --fast` erneut ausführen |

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
- optionaler Release-Statusabgleich über `RELEASE_READINESS_CURRENT_MAIN.md`
- bei CI-Laufzeitoptimierungen: ausgelagerte Suites weiter über `quality-gates` absichern (`tests/contracts`, `tests/integration/test_end_to_end_core_smoke.py`)
- `policy-baseline-validate` bei Änderungen an `.github/policy/branch_protection_baseline.json`

## Day-2 Routine

- Täglich vor Arbeitsstart: `git fetch --all --prune` + `git status --short --branch`.
- Vor jedem Push: ein lokaler Smokecheck.
- Bei roten Checks: zuerst Log analysieren, dann minimaler Fix.
- Bei roten CI-Runs: nur aktuelle, reproduzierbare Failures bearbeiten (keine historische Branch-Historie).

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
PYTHON=.venv/bin/python pytest -q tests/test_tool_interface.py
PYTHON=.venv/bin/python pytest -q tests/contracts/test_tool_contract_endpoints_presence.py
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
