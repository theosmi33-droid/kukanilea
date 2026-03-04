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
make bootstrap
make doctor
make test-smoke
```

Das Bootstrapping ist idempotent (`scripts/bootstrap.sh`) und setzt `.build_venv`, Python-Check via `.python-version`, Playwright und pre-commit Hooks auf.

## Development Targets

```bash
make bootstrap   # complete local setup
make doctor      # platform diagnostics (text)
./scripts/doctor.sh --json
make test-smoke  # fast corridor checks
make test-full   # complete pytest suite
```

Die vollständige Beschreibung ist in `docs/dev/BOOTSTRAP_AND_DOCTOR.md` dokumentiert.

## Data location (macOS)
By default, all writable data is stored under:
`~/Kukanilea/data/` (or configured via `KUKANILEA_USER_DATA_ROOT`)

See [CHANGELOG.md](CHANGELOG.md) for full details on the recent overhaul.
