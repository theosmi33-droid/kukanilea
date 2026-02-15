# Autonomy Source Scan v0

## Zweck
`Autonomy v0` automatisiert den lokalen Import in bestehende, gehärtete Pipelines:
- Dokumente (`document`)
- E-Mail (`email`, `.eml`/Maildir)
- Kalender (`calendar`, `.ics`)

Der Scanner ist offline-first, tenant-sicher und ohne neue Dependencies.

## Konfiguration
Scanner-Konfiguration wird tenant-bezogen in `source_watch_config` gespeichert:
- `documents_inbox_dir`
- `email_inbox_dir`
- `calendar_inbox_dir`
- `enabled`
- `max_bytes_per_file`
- `max_files_per_scan`

Wichtige Umgebungsvariablen:
- `KUKANILEA_ANONYMIZATION_KEY` (oder `ANONYMIZATION_KEY` im App-Config): Pflicht für `path_hash` HMAC
- `KUKANILEA_AUTONOMY_DOC_MAX_BYTES` (optional, Default 5MB)
- `KUKANILEA_BACKUP_DIR` (optional)
- `KUKANILEA_BACKUP_KEEP_DAYS` (optional, Default 7)

## Sicherheit
- Keine Rohpfade in `source_files`, `source_ingest_log` oder Eventlog (`path_hash` via HMAC)
- Keine PII in Event-Payloads (nur Hashes, IDs, Codes)
- READ_ONLY: Scan schreibt nicht und liefert `reason=read_only`
- Harte Limits: `max_files_per_scan`, `max_bytes_per_file`, Laufzeit-Budget
- Keine Netzwerk-/Exec-Pfade

## Ablauf
1. Kandidatendateien aus Inbox-Verzeichnissen sammeln (deterministisch sortiert)
2. `path_hash` + `fingerprint` berechnen
3. `source_files` upserten
4. Bei neuen/veränderten Dateien Delegation an vorhandene Ingest-Pipelines:
   - `knowledge_document_ingest`
   - `knowledge_email_ingest_eml`
   - `knowledge_ics_ingest`
5. Ergebnis in `source_ingest_log` und Eventlog dokumentieren (PII-frei)

## CLI
Scan ausführen:

```bash
python -m app.devtools.source_scan --tenant <TENANT_ID> --budget-ms 1500
```

Backup ausführen:

```bash
python -m app.devtools.maintenance --backup --tenant <TENANT_ID> --rotate
```

## Maildir-Hinweis
Für E-Mail kann lokal ein Maildir-Verzeichnis genutzt werden (`cur/`, `new/`, `tmp/`).
Der Scanner liest nur lokale Dateien, keine IMAP-Zugangsdaten.
