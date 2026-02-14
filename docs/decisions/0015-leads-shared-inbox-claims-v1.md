# 0015 — Leads Shared Inbox Claims v1

## Kontext

Bei Team-Inboxes entstehen Kollisionen, wenn mehrere Operatoren gleichzeitig denselben Lead bearbeiten. Ziel ist eindeutige Zuständigkeit ohne dauerhafte Blockade.

## Entscheidung

Wir führen `lead_claims` mit exklusiver Zuordnung pro `(tenant_id, lead_id)` ein.

- Claim ist explizit (kein Auto-Claim beim Öffnen).
- Claim hat TTL (Default 15 Minuten).
- Abgelaufene Claims können automatisch freigegeben werden.
- `force claim` ist erlaubt und wird als `reclaimed` auditiert.

## Security- und Audit-Regeln

- Tenant-Isolation in jeder Query.
- READ_ONLY blockiert alle mutierenden Claim-Aktionen.
- Eventlog schreibt pro Mutation genau ein Ereignis.
- Eventlog-Payload enthält keine PII-Textfelder.

## Konsequenzen

- Kollidierende Lead-Mutationen werden früh mit `409 lead_claimed` geblockt.
- UI zeigt Verantwortlichkeit (`frei`, `geclaimt`, `abgelaufen`) sichtbar an.
- Der Mechanismus bleibt offline-first und dependency-frei.
