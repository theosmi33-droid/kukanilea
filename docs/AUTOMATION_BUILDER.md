# Automation Builder v1

Stand: 2026-02-18

## Zweck
Der Automation Builder v1 verarbeitet tenant-spezifische Eventlog-Ereignisse und erzeugt daraus sichere Folgeaktionen.

Flow:
- Eventlog-Trigger wird abgeholt (cursor-basiert, idempotent).
- Regel-Trigger + Conditions werden geprueft (Allowlist, kein `eval`/`exec`).
- Actions werden entweder direkt ausgefuehrt (nur sichere Typen) oder als Pending Action abgelegt.
- Ausfuehrung wird im `automation_builder_execution_log` protokolliert.

## Sicherheitsgrenzen
- Kein automatischer E-Mail-Versand.
- Keine externen Requests/Webhooks.
- Pending Actions muessen serverseitig bestaetigt werden (`safety_ack`/`user_confirmed`).
- Pending-Confirm ist replay-sicher (one-time `confirm_token`, atomarer Consume).
- Pending-Confirm ist fuer `ADMIN`/`DEV` begrenzt.
- Browser-POSTs im Automation-Bereich sind CSRF-geschuetzt.
- Logs enthalten nur redigierte/technische Felder (IDs, Status, Trigger-Referenzen).
- Fail-closed: bei Fehlern oder ungueltiger Konfiguration keine unsichere Ausfuehrung.

## Trigger (v1)
- `eventlog`
  - `allowed_event_types` (Pflicht, Liste)
  - Beispiel:
```json
{
  "allowed_event_types": ["email.received", "lead.created"]
}
```

## Conditions (v1, Allowlist)
Unterstuetzte Operatoren:
- `equals`, `not_equals`
- `contains`, `not_contains`
- `starts_with`, `ends_with`
- `present`
- `all`, `any` (verschachtelt)

Nicht unterstuetzt:
- Regex
- dynamische Ausfuehrung
- Zugriff auf nicht-allowlistete Context-Felder

Beispiel:
```json
{
  "all": [
    {"field": "event_type", "equals": "email.received"},
    {"field": "from_domain", "contains": "@example.com"}
  ]
}
```

## Actions (v1)
Allowlist:
- `create_task`
- `create_postfach_draft`
- `create_followup`

Verhalten:
- Standard: pending (Confirm-Gate).
- Direktausfuehrung nur fuer nicht-destruktive Typen mit `requires_confirm=false`.
- `create_postfach_draft` bleibt confirm-gated.

## Idempotenz und Cursor
- Per tenant/source wird ein Cursor in `automation_builder_state` gefuehrt.
- Execution-Logs sind per `(tenant_id, rule_id, trigger_ref)` eindeutig.
- Bei Fehlern bleibt der Cursor auf dem letzten sicheren Punkt stehen.
- Per-Rule Rate-Limit: `max_executions_per_minute` (default: 10), Ueberschreitungen werden als `rate_limited` protokolliert.
- Reason-Codes in Execution-Logs: `ok`, `condition_false`, `action_pending`, `rate_limited`, `error_permanent:*`, `error_transient:*`.

## Manuelle Ausfuehrung
- UI: `POST /automation/run`
- Trigger aus Postfach-Sync: nach erfolgreichem IMAP-Sync wird `process_events_for_tenant()` aufgerufen.

## Pending Actions bestaetigen
- UI: `GET /automation/pending`
- Confirm: `POST /automation/pending/<id>/confirm` mit `safety_ack=1`
- Confirm verlangt zusaetzlich `confirm_token` (hidden POST field, kein Query-Parameter).

## Beispielregel (komplett)
```json
{
  "name": "Inbox -> Follow-up",
  "description": "Erzeuge Follow-up aus eingehender E-Mail",
  "is_enabled": true,
  "triggers": [
    {
      "trigger_type": "eventlog",
      "config": {"allowed_event_types": ["email.received"]}
    }
  ],
  "conditions": [
    {
      "condition_type": "field_match",
      "config": {"field": "event_type", "equals": "email.received"}
    }
  ],
  "actions": [
    {
      "action_type": "create_followup",
      "requires_confirm": true,
      "title": "Rueckruf aus Inbox"
    }
  ]
}
```

## Dry-Run / Simulation (v1.1)
- Regeltest ohne Seiteneffekte: `POST /automation/<rule_id>/simulate`
- Optional mit `event_id`, sonst wird das letzte passende Tenant-Event verwendet.
- Dry-Run schreibt einen `simulation`-Logeintrag, erzeugt aber keine echten Pending-Actions.

## Export / Import (safe JSON)
- Export: `GET /automation/<rule_id>/export`
- Import: `POST /automation/import` mit `rule_json`
- Import-Validierung ist strict (deny unknown fields), importierte Regeln starten immer deaktiviert (`is_enabled=false`).
