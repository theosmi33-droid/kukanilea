# Developer Bootstrap Flow (<10 Minuten)

Ziel: `clone -> bootstrap -> smoke tests` mit einem Time-to-green unter 10 Minuten.

## One-Command Setup

```bash
git clone <repo-url>
cd kukanilea
bash scripts/dev_bootstrap.sh
```

Der One-Command-Run erledigt automatisch:
1. Python-Basisauflösung mit Fallback-Policy (`PYTHON_BIN` → `pyenv` → `python3` → `python`)
2. `.venv` erstellen (falls nicht vorhanden)
3. Pip/Dev-Abhängigkeiten installieren (`requirements.txt` + `requirements-dev.txt`)
4. Playwright Browser installieren (`chromium`, inkl. `--with-deps`)
5. Doctor-Checks (`pytest`, `flask`, `ruff`, `playwright`)
6. Seed + Smoke (`scripts/seed_dev_users.py`, `scripts/seed_demo_data.py`, `python -m app.smoke`)
7. `scripts/ops/healthcheck.sh`
8. `scripts/ops/launch_evidence_gate.sh --fast`

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
scripts/dev/doctor.sh --strict
```

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

## Verifikation

```bash
PYTHON=.venv/bin/python scripts/ops/healthcheck.sh
PYTHON=.venv/bin/python scripts/ops/launch_evidence_gate.sh --fast
```

## Known issues / Fallback

- Wenn DB-Schreiben blockiert ist (read-only FS/DB-Lock), kann `seed_demo_data.py` fehlschlagen.
- Fallback:
  1. Read-only Fixtures verwenden (Smoke weiterhin ausführbar).
  2. Demo-Daten via manuellem SQL-Import in eine beschreibbare SQLite-Datei einspielen.
  3. Danach `KUKANILEA_AUTH_DB` auf diese Datei zeigen lassen und Seed erneut starten.
