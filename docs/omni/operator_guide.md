# Omni Assist v0 — Operator Guide

## CLI Ingest (Fixture-basiert)
Dry-Run (Default):
```bash
python -m app.devtools.cli_conversation_hub \
  --tenant TENANT_A \
  --channel email \
  --fixture /abs/path/to/file.eml \
  --json
```

Commit:
```bash
python -m app.devtools.cli_conversation_hub \
  --tenant TENANT_A \
  --channel email \
  --fixture /abs/path/to/file.eml \
  --commit \
  --json
```

## Scenario Runner
```bash
python -m app.devtools.conversation_scenarios \
  --tenant TENANT_A \
  --scenario email_with_pii \
  --json
```

```bash
python -m app.devtools.conversation_scenarios \
  --tenant TENANT_A \
  --scenario two_tenants \
  --json
```

## UI
- Übersicht: `/conversations`
- Detail: `/conversations/<event_id>`

## Erwartetes Verhalten
- Kein unredigierter PII-Text in persistierten Conversation-Events.
- Doppelte Ingests derselben Message werden dedupliziert.
- Tenant B sieht keine Events aus Tenant A.

