# Tasks Kanban Quickstart (Sprint 1 MVP)

## Ziel

Schnelltest fuer den ersten Kanban-Vertical-Slice (Create, Move, Done) im lokalen Setup.

## Voraussetzungen

- Lokales `main` mit Sprint-1 Kanban Branch.
- Tenant-Session als `OPERATOR`.
- READ_ONLY deaktiviert.

## Schritte

1. Tasks-Seite oeffnen:
```text
/tasks
```

2. Task anlegen (UI-Form):
- Titel setzen
- Optional `task_type`, `severity`, `details`

3. Task im Board verschieben:
- `Todo -> In Progress`
- `In Progress -> Done`

4. API-Sicht pruefen:
```text
/api/tasks?status=OPEN
/api/tasks?status=IN_PROGRESS
/api/tasks?status=RESOLVED
/api/tasks?status=ALL
```

5. READ_ONLY Verhalten pruefen:
- READ_ONLY aktivieren
- Create/Move muessen mit `read_only` blockieren

## Erwartung

- Tenant-Isolation bleibt erhalten.
- Mutationen funktionieren nur bei READ_ONLY=false.
- Keine neuen Dependencies oder externen Integrationen erforderlich.
