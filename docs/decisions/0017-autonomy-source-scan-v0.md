# ADR 0017: Autonomy Source Scan v0

## Status
Accepted

## Kontext
Das System hat bereits sichere Ingest-Pipelines (Knowledge, E-Mail, ICS), aber der Zufluss war überwiegend manuell.
Ziel ist eine lokale, reproduzierbare Automatisierung ohne neue Abhängigkeiten und ohne Netzwerkkopplung.

## Entscheidung
Wir führen einen lokalen Source-Scanner mit Polling ein:
- additive Tabellen: `source_watch_config`, `source_files`, `source_ingest_log`
- tenant-spezifische Inbox-Verzeichnisse für Dokumente, E-Mail und Kalender
- Delegation an bestehende, policy-gated Ingest-Module
- Laufzeit- und Größenlimits gegen DoS

Parallel ergänzen wir lokale Wartung:
- SQLite-Backup via `sqlite3.Connection.backup()`
- zeitbasierte Rotation alter Backups

## Sicherheitsentscheidungen
- Kein Netzwerkzugang im Scanner (kein IMAP/CalDAV in v0)
- Keine neuen Dependencies (Polling statt Watchdog)
- Keine Rohpfade im Audit: `path_hash` per HMAC-SHA256
- Eventlog-Payloads bleiben PII-frei (IDs/Hashes/Codes)
- READ_ONLY blockiert mutierendes Scanner-Verhalten fail-closed

## Folgen
- Höhere Autonomie bei gleicher Sicherheitsbasis
- Geringe Betriebsabhängigkeit (lokale Quellen reichen aus)
- Für Cloud-/Credential-basierte Connectoren bleibt ein späterer, separater Security-Entscheid nötig
