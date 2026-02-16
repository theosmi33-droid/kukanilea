# Sprint 1 — Tasks/Kanban Spec (v0)

## Ziel

Ein minimales, tenant-sicheres Task/Kanban-Backlog als Operator-Layer auf bestehender Architektur.

## Scope (v0)

- Task-Entity mit Status, Titel, Beschreibung, Prioritaet, Due-Date.
- Kanban-Board mit 3 Spalten:
  - `todo`
  - `in_progress`
  - `done`
- Tenant-Isolation in allen Queries (`tenant_id` Pflicht).
- READ_ONLY blockiert Mutationen.
- Eventlog fuer Mutationen, PII-sichere Payloads.

## Nicht im Scope

- Keine neuen Dependencies.
- Keine externen Integrationen.
- Keine Background-Worker.

## Datenmodell (Richtung)

- `tasks` (appenditiv, idempotente Schema-Erweiterung)
- optionale `task_events` fuer Audit-Trail

## API/UI Richtung

- Minimal CRUD fuer Tasks
- Drag/Drop optional spaeter; v0: explizite Status-Aktionen
- HTMX/HTML konsistent mit bestehendem Stil

## DoD

- Quality gates gruen
- Tenant-Tests vorhanden
- READ_ONLY-Tests vorhanden
- Eventlog-PII-Checks vorhanden
