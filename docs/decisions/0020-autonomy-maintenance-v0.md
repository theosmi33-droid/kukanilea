# ADR 0020: Autonomy Maintenance & Observability v0

## Status

Accepted

## Kontext

Autonomy verarbeitet lokale Quellen offline-first. Fuer den produktiven Betrieb fehlen ohne Maintenance-Funktionen jedoch:

- reproduzierbare Backups,
- nachvollziehbare Scanner-Laufhistorie,
- einfache Betriebsdiagnostik ohne externe Tools.

## Entscheidung

1. **SQLite Backup-API nutzen**
   - Backups via `sqlite3.Connection.backup()`, nicht ueber Dateikopie.
   - Direkte Verifikation im readonly-Modus.

2. **Maintenance-Status pro Tenant**
   - Tabelle `autonomy_maintenance_status` fuer letzte Laufdaten und Konfiguration.

3. **Scanner-Historie**
   - Tabelle `autonomy_scan_history` fuer deterministische Laufmetriken und Fehlerstatus.

4. **Log-Rotation lokal**
   - Komprimierung alter Logs mit stdlib `gzip`.
   - Entfernen alter Archive gemaess Aufbewahrungsfenster.

5. **READ_ONLY fail-closed**
   - Maintenance-Mutationen werden in READ_ONLY blockiert.

## Sicherheitsaspekte

- Keine neuen Dependencies.
- Keine Netzwerkverbindungen.
- Eventlog-Payloads bleiben PII-frei (IDs, Counts, Reason-Codes).

## Konsequenzen

- Bessere Betriebsstabilitaet bei weiterhin lokaler/offline Architektur.
- Nachvollziehbare Scanner- und Maintenance-Laeufe.
- Keine Abhaengigkeit von externen Backup-/Log-Tools in v0.
