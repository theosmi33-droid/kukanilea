# Kanban Domain Model (projekte)

## Tabellen
- `project_boards`
  - Board-Metadaten pro Projekt und Tenant
- `project_columns`
  - Spalten pro Board mit `position`, `color`, `archived`
- `project_cards`
  - Karten mit `title`, `description`, `due_date`, `assignee`, `linked_task_id`, `column_id`, `position`
- `card_comments`
  - Kommentare je Karte
- `card_attachments`
  - Anhangsreferenzen je Karte (`file_path`, `file_name`)
- `card_activities`
  - Aktivitaets-Events fuer Board/Card-Aktionen

## Aktivitaetslogging
Jede relevante Mutation schreibt:
1. `audit_log` (globales Audit)
2. `card_activities` (board-spezifischer Verlauf)
3. `agent_memory` (semantische Historie fuer KI-Abfragen)

## API-Endpunkte
- `GET /api/projects/state?board_id=...`
- `POST /api/projects`
- `POST /api/projects/boards`
- `POST /api/projects/columns`
- `PATCH /api/projects/columns/<column_id>`
- `DELETE /api/projects/columns/<column_id>`
- `POST /api/projects/cards`
- `PATCH /api/projects/cards/<card_id>`
- `POST /api/projects/cards/<card_id>/move`
- `GET/POST /api/projects/cards/<card_id>/comments`
- `GET/POST /api/projects/cards/<card_id>/attachments`
- `POST /api/projects/cards/<card_id>/link-task`
- `POST /api/projects/cards/<card_id>/start-timer`

## Integrationen
- Task-Link: nutzt `task_create` falls verfuegbar, ansonsten kann `task_id` uebergeben werden.
- Timer: nutzt `time_entry_start` falls verfuegbar.

## Tenant-Sicherheit
Alle CRUD-Abfragen sind tenant-gebunden. Fremdmandantenzugriffe liefern `403 forbidden`.
