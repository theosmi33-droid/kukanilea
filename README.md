# KUKANILEA (macOS, local-first)

Referenzen:
- Onboarding: `ONBOARDING.md`
- Weekly Review: `WEEKLY_TEMPLATE.md`
- Glossar: `GLOSSARY.md`
- Teamrollen: `TEAM_ROLES.md`
- Verfassung: `docs/CONSTITUTION.md`
- Konfiguration: `docs/CONFIGURATION.md`
- TEXT-ID Migration: `docs/runbooks/text_id_migration_plan.md`

## End-user install (DMG)
1. Open `KUKANILEA.dmg`.
2. Drag `KUKANILEA.app` to `Applications`.
3. Start the app and open [http://127.0.0.1:5051](http://127.0.0.1:5051).

KUKANILEA runs local-only and binds to `127.0.0.1`.

## Data location (macOS)
All writable data is stored under:
`~/Library/Application Support/KUKANILEA/`

Files include:
- `auth.sqlite3`
- `core.sqlite3`
- `license.json`
- `trial.json`
- `logs/`

## Licensing and trial
- No online license validation.
- If `license.json` is missing, a 14-day trial starts on first run (`trial.json`).
- If trial expires, license expires, or device binding mismatches, app enters read-only mode.
- Read-only mode blocks all `POST/PUT/PATCH/DELETE` requests server-side (HTTP 403).

### Apply a license
Place a signed `license.json` into:
`~/Library/Application Support/KUKANILEA/license.json`

## Run (production entrypoint)
```bash
python kukanilea_app.py
```

## Build artifacts
```bash
bash scripts/release_zip.sh
bash scripts/build_mac.sh
bash scripts/make_dmg.sh
```

## Developer checks
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m app.smoke
```
