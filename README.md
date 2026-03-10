# KUKANILEA

🚀 **Local-First Enterprise Intelligence**

KUKANILEA ist eine local-first und offline-first Arbeitsplattform für Handwerk und Mittelstand. Die MIA-gestützte Ausführung bleibt auditierbar, deterministisch und Sovereign-11-kompatibel.

## Recent Updates (v1.0.0-beta.3)

✅ **Production-Ready Transformation Complete**
- **Clean Architecture:** Blueprint-based HMVC structure.
- **Premium UI/UX:** Pro design system with system fonts & haptics.
- **Hardened Security:** ClamAV scanning & strict CSP.
- **Fast Performance:** Parallelized testing & SQLite WAL mode.

## End-user install (DMG)
1. Open `KUKANILEA.dmg`.
2. Drag `KUKANILEA.app` to `Applications`.
3. Start the app and open [http://127.0.0.1:5051](http://127.0.0.1:5051).

## Quickstart (<10 min)

```bash
# 1) Clone + bootstrap (inkl. Healthcheck + Smoke) in einem Lauf
git clone <repo-url>
cd kukanilea
bash scripts/dev_bootstrap.sh

# 2) One-command dev start
bash scripts/dev_run.sh
```

`scripts/dev_bootstrap.sh` umfasst venv+deps, Playwright-Browser, Doctor-Checks, Healthcheck, Smoke und Launch-Evidence (`--fast`).
`scripts/dev_run.sh` startet reproduzierbar über denselben `.venv`-Interpreter und führt Bootstrap bei Bedarf automatisch aus.

### Verifikation (Time-to-Green)

```bash
bash -n scripts/dev_bootstrap.sh scripts/dev_run.sh scripts/ops/healthcheck.sh scripts/ops/launch_evidence_gate.sh
./scripts/ops/healthcheck.sh
scripts/ops/launch_evidence_gate.sh
```

Weitere Details: `docs/dev/BOOTSTRAP_QUICKSTART.md`

## Token-saver Workflow (für schnelle Debug/PR-Zyklen)

```bash
# Zielgerichtete Suche statt Vollausgabe
rg -n "bootstrap|healthcheck|smoke|doctor" README.md docs/dev/BOOTSTRAP_QUICKSTART.md scripts/

# Kleine, fokussierte Diffs statt riesiger Kontext-Blöcke
git diff -- README.md docs/dev/BOOTSTRAP_QUICKSTART.md

# Selektiv anzeigen (z. B. nur erste 120 Zeilen)
sed -n '1,120p' docs/dev/BOOTSTRAP_QUICKSTART.md
```

Regel: `rg`/`grep -n` bevorzugen, keine großen `cat`-Dumps über ganze Verzeichnisbäume, und Diffs immer dateiweise eingrenzen.

### Tool Interface Verification

```bash
python scripts/dev/verify_tools.py
```

Der Check lädt alle Tool-Module dynamisch, validiert den Core-Tool-Interface-Contract und liefert einen klaren Exitcode ungleich 0 bei fehlerhaften Tools.

## Quick Start (Developer)

```bash
# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start the full-stack system
# (optional for development: export KUKANILEA_ENV=development)
python run.py server --host 127.0.0.1 --port 5051
```

## Data location (macOS)
By default, all writable data is stored under:
`~/Kukanilea/data/` (or configured via `KUKANILEA_USER_DATA_ROOT`)

See [CHANGELOG.md](CHANGELOG.md) for full details on the recent overhaul.

## PR Quality Guard

Für PR-Qualität ist ein Hard-Gate aktiv:

```bash
bash scripts/dev/pr_quality_guard.sh --ci
```

Regeln:
- MAX_SCOPE: `<= 12` Dateien **und** `<= 350` LOC
- Focused Scope: höchstens `3` Änderungsbereiche (Top-Level + Subpfad)
- MIN_TESTS: `>= 6` Test-Delta
- Evidence Report: `docs/reviews/codex/PR_QUALITY_GUARD_REPORT_20260305.md`
- Main-first: Basis muss `origin/main` sein
- Shared-Core Hotspots (`app/web.py`, `app/core/logic.py`, `app/__init__.py`, `app/db.py`, `app/templates/layout.html`) sind im gemischten PR gesperrt

Details im Contributing Guide: [CONTRIBUTING.md](CONTRIBUTING.md).

## Main-Only Branch Policy

- `main` is the single source of truth.
- Every PR must target `main`.
- Start each new task from latest `origin/main`.
- Do not chain new work on stale feature branches.

Policy detail: `docs/policies/MAIN_ONLY_SOURCE_OF_TRUTH.md`.

Für Lane-Resubmit/Open-PR-Check (mit `gh`-Fallback auf GitHub-API):

```bash
bash scripts/dev/open_pr_status.sh --repo theosmi33-droid/kukanilea --state open
```
