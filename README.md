# KUKANILEA Business OS

🚀 **Local-First Enterprise Intelligence**

KUKANILEA is a modern, high-performance Business Operating System designed for the craft and trade industries. It combines local AI capabilities with enterprise-grade stability and security.

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
# 1) Clone + reproducible bootstrap in one run
git clone <repo-url>
cd kukanilea
bash scripts/dev_bootstrap.sh

# 2) One-command dev start
bash scripts/dev_run.sh
```

`scripts/dev_bootstrap.sh` umfasst venv+deps, Playwright-Browser, Doctor-Checks, Smoke, Healthcheck und Launch-Evidence (`--fast`).
`scripts/dev_run.sh` startet reproduzierbar über denselben `.venv`-Interpreter und führt Bootstrap bei Bedarf automatisch aus.

### Verifikation (Time-to-Green)

```bash
bash -n scripts/dev_bootstrap.sh scripts/dev_run.sh scripts/ops/healthcheck.sh scripts/ops/launch_evidence_gate.sh
./scripts/ops/healthcheck.sh
scripts/ops/launch_evidence_gate.sh
```

Weitere Details: `docs/dev/BOOTSTRAP_QUICKSTART.md`

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
