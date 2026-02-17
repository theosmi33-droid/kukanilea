## Why
- Wiederkehrende Intake-Prozesse sollen aus Eventlog-Ereignissen automatisiert werden.
- Builder v1 liefert einen sicheren End-to-End-Pfad: Trigger -> Conditions -> Actions -> Execution Log.
- Kritische Aktionen sind confirm-gated; unsichere oder unbekannte Pfade laufen fail-closed.

## Scope
- Runner-Status und Cursor-Tracking:
  - `automation_builder_state` fuer source-cursor pro Tenant.
  - Idempotenzindex auf `automation_builder_execution_log(tenant_id, rule_id, trigger_ref)`.
- Eventlog Trigger-Quelle:
  - synchroner Runner `process_events_for_tenant()`.
  - Cursor-basierte Verarbeitung, tenant-scope, duplicate-safe.
- Conditions Engine (allowlist):
  - Operatoren: `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `ends_with`, `present`, `all`, `any`.
  - keine Regex, kein eval/exec.
- Actions v1 (allowlist):
  - `create_task`, `create_postfach_draft`, `create_followup`.
  - pending-by-default + confirm gate.
- Web UI:
  - `/automation` (Regelliste v1)
  - `/automation/<rule_id>` (Details)
  - `/automation/<rule_id>/logs` (Execution-Logs)
  - `/automation/pending` (pending actions)
  - `POST /automation/pending/<id>/confirm` (serverseitige Bestätigung mit `safety_ack`)
  - `POST /automation/run` (manueller Runner)
- Doku:
  - `docs/AUTOMATION_BUILDER.md`
  - `ONBOARDING.md` Abschnitt fuer Builder v1

## Security Invariants
- Fail-closed bei unklaren/ungueltigen Pfaden.
- Tenant-Isolation in allen Builder-Queries.
- Keine dynamische Ausfuehrung (`eval`/`exec`), keine Shell-Execution.
- Keine PII in Runner-/Execution-Payloads (nur IDs/Status/Redacted-Summary).
- Kein automatischer E-Mail-Versand in Builder v1.
- Kritische Aktionen nur mit serverseitigem Confirm-Gate (`safety_ack`/`user_confirmed`).

## How to Verify
```bash
python -m compileall -q . && echo "compileall rc=$?"
ruff check . && echo "ruff check rc=$?"
ruff format . --check && echo "ruff format rc=$?"
pytest -q && echo "pytest rc=$?"
python -m app.devtools.security_scan && echo "security_scan rc=$?"
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)" && echo "triage rc=$?"
python -m app.devtools.schema_audit --json > /dev/null && echo "schema_audit rc=$?"
```

Manuell:
1. `/automation` oeffnen, Regelstatus toggeln.
2. Event erzeugen (z. B. Postfach-Sync), danach `/automation/<rule_id>/logs` pruefen.
3. Pending Action auf `/automation/pending` bestaetigen.
4. Confirm ohne `safety_ack` pruefen (muss blockieren).

## Risks & Rollback
- Risiken:
  - Eventlog-Tenant-Zuordnung basiert auf `payload.tenant_id`; Events ohne Tenant-Info werden fail-closed ignoriert.
  - Runner v1 ist synchron (noch kein Background-Worker).
- Rollback:
  - atomare Commits, einzeln revertierbar.
  - Schema ist additiv/idempotent; keine destruktiven Drops.

## Out of Scope
- Automatischer Mailversand.
- Webhook-/HTTP-Actiontypen.
- Visual Rule Builder (JSON-only v1).
- Benutzerdefinierte Triggerquellen ausser Eventlog.
