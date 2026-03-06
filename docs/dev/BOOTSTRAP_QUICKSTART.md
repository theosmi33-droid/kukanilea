# Developer Bootstrap Flow (<10 Minuten)

Ziel: `clone -> bootstrap -> smoke tests -> healthcheck` reproduzierbar unter 10 Minuten.

## One-Command Setup

```bash
git clone <repo-url>
cd kukanilea
bash scripts/dev_bootstrap.sh
```

Der One-Command-Run erledigt automatisch:
1. Python-Basisauflösung mit Fallback-Policy (`PYTHON_BIN` → `.python-version` via `pyenv` → `python3` → `python`)
2. `.venv` erstellen (falls nicht vorhanden)
3. Pip/Dev-Abhängigkeiten installieren (`requirements.txt` + `requirements-dev.txt`)
4. Playwright Browser installieren (`chromium`, lokal via `python -m playwright install`)
5. Doctor-Checks (`pytest`, `flask`, `ruff`, `playwright`)
6. Seed + Smoke (`scripts/seed_dev_users.py`, `scripts/seed_demo_data.py`, `python -m app.smoke`)
7. `scripts/ops/healthcheck.sh`
8. `scripts/ops/launch_evidence_gate.sh --fast`

## Repro-Runbook (exakte Kommandos)

```bash
# 0) Frischer Clone
git clone <repo-url>
cd kukanilea

# 1) Bootstrap (führt Healthcheck + Smoke automatisch aus)
bash scripts/dev_bootstrap.sh

# 2) Einzelprüfungen explizit wiederholbar
./scripts/ops/healthcheck.sh
python -m app.smoke
```

Zeitmessung (optional, für CI/DevEx-Nachweis):

```bash
time bash scripts/dev_bootstrap.sh
```

## Python-Fallback (robust)

Globale Policy für Shell-Skripte:
1. `PYTHON` (explizit gesetzt)
2. `.venv/bin/python`
3. `pyenv which python` (wenn verfügbar)
4. `python3`
5. `python`

Resolver: `scripts/dev/resolve_python.sh`

## Hilfreiche Flags

```bash
# Nur Setup ohne Seeds
bash scripts/dev_bootstrap.sh --skip-seed

# Healthcheck / Launch-Evidence separat skippen
bash scripts/dev_bootstrap.sh --skip-healthcheck --skip-launch-evidence

# Tool-Diagnose standalone
scripts/dev/doctor.sh --strict          # lokal: Browser-Binaries nur Warnung
scripts/dev/doctor.sh --strict --ci     # CI: Browser-Binaries Pflicht
```


## Doctor Playwright Semantik

`doctor.sh` trennt die Playwright-Prüfungen jetzt explizit:
- Python-Modul `playwright` vorhanden (Pflicht)
- Python-CLI via `python -m playwright` nutzbar (Pflicht)
- Node-CLI `playwright` im `PATH` (optional, nur Hinweis)
- Chromium-Browser-Binary installiert (`--ci` Pflicht, lokal nur Warnung)

Recovery-Hinweise stehen direkt in den FAIL/WARN-Meldungen.

## App starten

```bash
bash scripts/dev_run.sh
```

Optionale Flags:

```bash
# vorhandenes Setup nicht erneut bootstrapen
bash scripts/dev_run.sh --skip-bootstrap

# Seed beim Start überspringen
bash scripts/dev_run.sh --skip-seed
```

## Pflicht-Verifikation

```bash
bash -n scripts/dev_bootstrap.sh scripts/dev_run.sh scripts/ops/healthcheck.sh scripts/ops/launch_evidence_gate.sh
./scripts/ops/healthcheck.sh
scripts/ops/launch_evidence_gate.sh
```

## Token-saver Workflow

```bash
# Suchraum klein halten
rg -n "healthcheck|smoke|bootstrap|doctor" docs/dev/BOOTSTRAP_QUICKSTART.md README.md scripts/

# Statt großer Dumps gezielte Ausschnitte lesen
sed -n '1,140p' docs/dev/BOOTSTRAP_QUICKSTART.md

# Nur betroffene Dateien diffen
git diff -- docs/dev/BOOTSTRAP_QUICKSTART.md README.md
```

Leitlinie: erst `rg`/`grep -n`, dann kleine Ausschnitte/targeted diffs; keine absoluten Pfade und keine ungerichteten Full-File/Tree-Ausgaben.

## Known issues / Fallback

- Wenn DB-Schreiben blockiert ist (read-only FS/DB-Lock), kann `seed_demo_data.py` fehlschlagen.
- Fallback:
  1. Read-only Fixtures verwenden (Smoke weiterhin ausführbar).
  2. Demo-Daten via manuellem SQL-Import in eine beschreibbare SQLite-Datei einspielen.
  3. Danach `KUKANILEA_AUTH_DB` auf diese Datei zeigen lassen und Seed erneut starten.
