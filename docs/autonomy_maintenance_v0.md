# Autonomy Maintenance v0

Dieses Paket erweitert Autonomy um Betriebsfunktionen fuer Stabilitaet und Nachvollziehbarkeit:

- Backup mit SQLite-Backup-API (`sqlite3.Connection.backup()`).
- Backup-Verifikation (readonly-Open + `SELECT COUNT(*)`).
- Log-Rotation (gzip + Loeschen alter Archive).
- Scanner-Historie und Health-Uebersicht pro Tenant.
- Smoke-Test fuer Basischecks.

## READ_ONLY Verhalten

- Mutierende Maintenance-Aktionen sind in READ_ONLY blockiert:
  - `run_backup`
  - `rotate_logs`
  - `run_smoke_test`
- Scanner schreibt in READ_ONLY keine Historie.

## Backup

- Zielverzeichnis: `KUKANILEA_BACKUP_DIR` oder Default unter User-Data.
- Struktur: `<backup_root>/<tenant>/backup-YYYYMMDD-HHMMSS.sqlite`
- Rotation ueber `backup_keep_days` (Default 7).
- Nach Erstellung: Verifikation im readonly-Modus.

## Log-Rotation

- Log-Verzeichnis: `KUKANILEA_LOG_DIR` oder Default unter User-Data.
- Alte `.log` Dateien werden gzip-komprimiert.
- Alte `.gz` Archive werden nach `log_keep_days` entfernt.

## Health Dashboard

Route: `/autonomy/health`

Zeigt:
- letzter Scanlauf + Kennzahlen
- Backup-Status + Verifikationsflag
- letzte Log-Rotation
- letztes Smoke-Test-Ergebnis

## Eventlog (PII-frei)

Maintenance-Events enthalten nur technische Kennzahlen und Reason-Codes, keine Rohpfade oder Inhalte:

- `maintenance_backup_ok`
- `maintenance_backup_failed`
- `maintenance_logs_rotated`
- `maintenance_smoke_test`
