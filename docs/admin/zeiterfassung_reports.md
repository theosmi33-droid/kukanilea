# Zeiterfassung Reports (Admin/Boss)

## Rechte
- `ADMIN`/`DEV`: Teamweite Sicht auf Zeiten und Reports.
- `OPERATOR`: Nur eigene Zeiten.

## Team-Übersicht
Im Zeit-Tab steht für Admins ein Reporting-Panel zur Verfügung:
- Aggregation nach Nutzer
- Aggregation nach Projekt
- Totals:
  - aktive Dauer
  - stornierte Dauer
  - Anzahl Einträge

Zeiträume:
- `Tag`
- `Woche`
- `Monat`
- `Jahr`

## GoBD-Prinzip
- Keine physische Löschung von Zeitbuchungen.
- Korrektur ausschließlich per `Storno`:
  - `is_cancelled = 1`
  - `cancelled_by`, `cancelled_at`, `cancel_reason`

## CSV-Export (Steuerbüro)
Der Export enthält zusätzliche Nachvollziehbarkeit:
- Zeitfenster (`export_scope_start`, `export_scope_end`)
- Nutzer/Projekt/Task-Bezug
- Storno-Felder
- Hash-Verkettung (`entry_hash`, `previous_entry_hash`)

Damit bleibt die Exportliste prüfbar und unveränderbare Historie ist nachvollziehbar.
