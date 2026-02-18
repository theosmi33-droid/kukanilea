## Title
feat(automation): Phase 3.3 – Cron-Trigger und E-Mail-Entwurf-Aktion

## Why
- Zeitgesteuerte Regeln (Cron) erweitern den Builder über reine Eventlog-Trigger hinaus.
- `email_draft` erlaubt automatisierte Kommunikationsvorbereitung ohne Auto-Send.
- Sicherheitsprinzipien bleiben erhalten: fail-closed, tenant-scoped, kein Versand ohne explizite Bestätigung.

## Scope
- Neuer Cron-Parser (`*` + feste Zahlen) in `app/automation/cron.py`.
- Runner-Erweiterung für Cron-Trigger inklusive minute-genauer Idempotenz (`trigger_ref`).
- Optionaler lokaler Cron-Checker-Thread (konfigurierbar, in Tests deaktiviert).
- Neue Action `email_draft` in `app/automation/actions.py`.
- CRM-Empfängerprüfung über `contacts` (tenant-scoped) vor Draft-Erzeugung.
- Fallback auf erstes konfiguriertes Postfach-Konto, wenn `account_id` fehlt.
- Builder-UI erweitert: Cron-Trigger hinzufügen, `email_draft`-Action hinzufügen.
- Import-Validierung erweitert: `cron` und `email_draft` mit sicherer Strukturprüfung.
- Tests + Doku aktualisiert.

## Security Invariants
- Kein automatischer E-Mail-Versand (nur Draft-Erzeugung).
- Empfänger für `email_draft` müssen im CRM des Tenants existieren.
- Keine neuen Dependencies.
- Cron-Trigger dedupliziert pro Minute via unique `trigger_ref`.
- Pending-/Confirm-Mechanik bleibt serverseitig erzwungen.

## How to verify
```bash
cd /Users/gensuminguyen/Tophandwerk/kukanilea-git
source .venv/bin/activate
python -m compileall -q .
ruff check .
ruff format . --check
pytest -q
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
python -m app.devtools.schema_audit --json > /dev/null
```

## Manual checks
1. In `/automation/<rule_id>` Cron-Trigger via Formular hinzufügen (`0 8 * * 1`).
2. `email_draft`-Action mit Empfänger + Betreff + Body hinzufügen.
3. Regel-Simulation ausführen und Logs in `/automation/<rule_id>/logs` prüfen.
4. Optional: `/automation/run` ausführen und Cron-/Eventlog-Ergebnis prüfen.

## Risks & Rollback
- Risiko: falsch konfigurierte Cron-Ausdrücke feuern nicht (fail-closed).
- Risiko: fehlende CRM-Kontakte blockieren `email_draft` (beabsichtigt).
- Rollback: PR vollständig revertierbar; keine destruktiven Migrationen.

## Out of scope
- Kein automatischer SMTP-Versand durch Automation.
- Keine erweiterten Cron-Syntax-Features (`*/15`, Bereiche, Listen) in v1.
- Keine neuen externen Triggerquellen außer Eventlog/Cron.
