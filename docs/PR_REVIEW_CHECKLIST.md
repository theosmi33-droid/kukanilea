# PR Review Checklist

## Core-Freeze
- [ ] Keine neuen Dependencies ohne ADR (`docs/adr/ADR-*.md`).
- [ ] Stack-Aenderungen sind dokumentiert und begruendet.

## Security & Compliance
- [ ] Keine PII in Eventlog/Telemetry-Payloads.
- [ ] Token/Code-Vergleiche nutzen `secrets.compare_digest()`.
- [ ] `subprocess` mit `shell=False` und `timeout`.
- [ ] OCR/Mail-Daten vor Persistenz redigiert.
- [ ] READ_ONLY-Guards fuer Mutationen vorhanden.

## Multi-Tenant
- [ ] Jede relevante Query tenant-scoped (`tenant_id`).
- [ ] Keine Cross-Tenant Sichtbarkeit in API/UI.

## Datenbank
- [ ] Migrationen sind additiv und idempotent (`CREATE TABLE IF NOT EXISTS`).
- [ ] Neue Tabellen/Entitaeten nutzen TEXT IDs.

## Tests & Quality
- [ ] Neue/veraenderte Security-Pfade sind getestet.
- [ ] `ruff check . --fix`, `ruff format .`, `pytest -q` gruene lokale Runs.
- [ ] `python -m app.devtools.triage --ci --fail-on-warnings` erfolgreich.

## Doku
- [ ] README/Runbook/Onboarding aktualisiert.
- [ ] Repro-Schritte und Rollback-Hinweis in PR beschrieben.
