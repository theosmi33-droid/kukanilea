## Why
Pilot-Readiness ist der naechste Meilenstein. Dieser PR legt die Grundlage fuer 3-5 Pilotkunden mit reproduzierbaren Demo-Daten und belastbarer Auswertung.

## What
- Idempotentes Seed-Skript: `scripts/seed_demo_data.py`
  - legt Demo-Tenant inkl. `demo/demo` an
  - erstellt 5 Kontakte, 10 Dokumente, 3 Tasks, 1 Automation-Regel
  - nutzt Service-Layer (CRM, Tasks, Lead-Intake, Source-Scan, Automation Store)
  - `--force` fuer reproduzierbaren Neuaufbau
- Erweitertes Support-Bundle: `pilot_metrics.json`
  - Logins (14d), Dokumente, Tasks, Automation-Ausfuehrungen, aktive Regeln, letzte Aktivitaet
  - nur aggregierte Werte, keine PII
- Pilot-Dokumentation
  - `docs/runbooks/pilot_v1.md`
  - `docs/pilot_feedback.md`
  - Verweise in `ONBOARDING.md` und `docs/CONFIGURATION.md`

## How to test
```bash
python scripts/seed_demo_data.py --tenant-name "DEMO AG"
python scripts/seed_demo_data.py --tenant-name "DEMO AG" --force
pytest -q tests/test_demo_data.py tests/test_seed_demo.py tests/test_support_bundle_metrics.py tests/test_devtools_support_bundle.py
```

## Security invariants
- Beispieldaten sind fiktiv (`@demo.invalid`, Platzhalter-Telefonnummern)
- Seed schreibt Domain-Daten ueber Service-Layer
- Pilot-Metriken enthalten keine Einzeltransaktionen/PII

## Verify gates
- `python -m compileall -q .` rc=0
- `ruff check .` rc=0
- `ruff format . --check` rc=0
- `pytest -q` rc=0 (`423 passed`)
- `python -m app.devtools.security_scan` rc=0
- `python -m app.devtools.triage --ci --fail-on-warnings ...` rc=0
- `python -m app.devtools.schema_audit --json > /dev/null` rc=0

## Rollback
Revert des PRs. Seed ist idempotent und erzeugt ohne `--force` keine Duplikate.
