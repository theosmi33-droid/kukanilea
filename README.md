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

## Quick Start (Developer)

```bash
# One-command bootstrap (creates .build_venv, installs deps, playwright, pre-commit)
make bootstrap

# Validate local toolchain
make doctor

# Start the full-stack system
# (optional for development: export KUKANILEA_ENV=development)
./.build_venv/bin/python kukanilea_app.py --host 127.0.0.1 --port 5051
```

See [docs/dev/BOOTSTRAP_AND_DOCTOR.md](docs/dev/BOOTSTRAP_AND_DOCTOR.md) for troubleshooting and CI parity.

## Data location (macOS)
By default, all writable data is stored under:
`~/Kukanilea/data/` (or configured via `KUKANILEA_USER_DATA_ROOT`)

See [CHANGELOG.md](CHANGELOG.md) for full details on the recent overhaul.
