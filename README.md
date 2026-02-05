# KUKANILEA Systems — Agent Orchestra (Local)

## What this bundle contains
- `kukanilea_app.py` — single entry point (uses `create_app()` in `app/`).
- `app/` — app factory, auth, db, web routes.
- `kukanilea_core_v3_fixed.py` — core logic (DB, ingest, OCR/extract, archive rules).
- `kukanilea_weather_plugin.py` — optional weather helper.
- `requirements.txt` — minimal Python deps.
- `scripts/start_ui.sh` — zsh-safe starter.
- `scripts/dev_run.sh` — idempotent dev runner (seeds users).

## Quick start (macOS)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_dev_users.py
python kukanilea_app.py
```
Open: http://127.0.0.1:5051

**Logins**
- `admin/admin` → Tenant: **KUKANILEA** (ADMIN)
- `dev/dev` → Tenant: **KUKANILEA Dev** (DEV)

### One-command dev run
```bash
./scripts/dev_run.sh
```

### Dev bootstrap
```bash
./scripts/dev_bootstrap.sh
```

## Notes
- Tenant is derived from account membership and never entered in the UI.
- If you see a `zsh: parse error near ')'`, use `scripts/start_ui.sh` or `scripts/dev_run.sh` instead of copying numbered lists.

## Known Limits
- OCR fallback depends on system tools (tesseract/poppler) if enabled.
- Search may fall back to DB/FS if FTS is unavailable.

## Docs
- `docs/ARCHITECTURE.md`
- `ROADMAP.md`
- `PACKAGING.md`
