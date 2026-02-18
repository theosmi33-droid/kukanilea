# Repo Overview

## Zweck
KUKANILEA ist eine lokale, mandantenfähige Dokument-/Agent-Orchestrierung mit Upload-Review-Ablage-Pipeline, Policy-Gates und Audit-Logging.
Quellen: `README.md`, `docs/ARCHITECTURE.md`, `PROJECT_STATUS.md`.

## Start / Betrieb
- Haupt-Entry-Point: `python kukanilea_app.py` (delegiert auf `create_app()` in `app/__init__.py`).
- Flask-CLI (Factory): `flask --app app run --port 5051`.
- Dev-Skripte:
  - `./scripts/dev_run.sh`
  - `./scripts/dev_bootstrap.sh`

## Test / Qualität
- Lint/Fix: `ruff check . --fix`
- Format: `ruff format .`
- Tests: `pytest -q`
- Smoke: `python -m app.smoke`

## Ordnerkarte (Top-Level, funktional)
- `app/`: Flask App Factory, Auth, DB, Fehler-/Logging-Handling, Web-Blueprint
- `kukanilea/`: Agenten + Orchestrator + Policy
- `tests/`: Pytest-Suite inkl. Security/Orchestrator/Smoke-nahe Tests
- `docs/`: Architektur, ADRs, Spezifikationen
- `contracts/`: Schema-/Contract-Dateien
- `scripts/`: Dev/Build/Seed-Utilities
- `archive/legacy/`: historischer Restbestand (Legacy-Dateien wurden zusätzlich nach `nousage/legacy_candidates/` verschoben)
- `reports/`: technische Reports (u. a. Cleanup)

## Datenfluss (faktenbasiert)
1. Upload erfolgt über UI/API (`/upload`).
2. Analyse schreibt Pending-Status; Review-Flows laufen über `/review/...`.
3. Re-Extract und Process verwenden Resolver-Logik (stale `pending.path` -> DB `versions.file_path` fallback mit Allowlist).
4. Orchestrator route't Intents auf Agents und prüft vor Actions die Policy (`deny-by-default`).
5. Safe-Mode wird im Orchestrator-Kontext verarbeitet (`allow_llm = not safe_mode`).

## Konfiguration / Env-Variablen
Im Code werden sowohl `KUKANILEA_*` als auch `TOPHANDWERK_*` Variablen verwendet (Alias-Muster via `_env(...)`).
Wichtige Gruppen:
- App/Server: `PORT`, `SECRET`, API-Keys
- Pfade: `EINGANG_DIRNAME`, `BASE_DIRNAME`, `PENDING_DIRNAME`, `DONE_DIRNAME`, `DB_FILENAME`
- Tenant/Rollen: `TENANT_DEFAULT`, `TENANT_REQUIRE`, `TENANTS`
- Upload/Processing Limits: `MAX_UPLOAD`, OCR-/Extraction-bezogene Parameter
- Feature-Flags: u. a. FS-Scan-Fallback (`KUKANILEA_ENABLE_FS_SCAN_FALLBACK`, default aus)

Vollständige, aus dem Code extrahierte Liste liegt unter:
- `reports/zip_sync/20260211_100735/env_vars_detected.txt`
- `reports/zip_sync/20260211_100735/env_vars_detected.json`

## Bekannte Punkte (aus Code/Tests)
- OCR-Fallback hängt von lokal installierten System-Tools ab (README-Hinweis).
- FS-Search-Fallback ist absichtlich standardmäßig deaktiviert und nur per DEV-Flag aktivierbar.


## Nächste sichere Verbesserungen

- Weitere Bereinigung historischer, aber getrackter Legacy-Dateien nur nach expliziter Freigabe.
- Env-Variablen-Dokumentation als stabile Tabelle in `docs/` verstetigen.
