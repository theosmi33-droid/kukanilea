# ADR 0018: Autonomy Phase 2a (Excludes, Tags, Filename Metadata)

## Status
Accepted

## Kontext
Der Scanner aus Phase 1 verarbeitet lokale Quellen robust, benötigt aber bessere Hygiene und Struktur:
- technische Ausschlussmuster
- tenant-sichere, globale Labels
- leichte Metadaten ohne Inhaltszugriff

## Entscheidung
1. Exclude-Globs in `source_watch_config` (JSON, validiert)
2. Globales Tag-Modul (`app/tags/core.py`) mit eigenen Tabellen
3. Metadaten aus Dateiname/Pfad in `source_files.metadata_json`

## Begründung
- Excludes reduzieren Rauschen und vermeiden ingest von technischen Artefakten.
- Tags sind querschnittlich und sollen nicht an eine einzelne Domäne gekoppelt sein.
- `name_norm` verhindert Case-Duplikate konsistent pro Tenant.
- Eventlog enthält keine Tag-Namen (PII-Risiko), nur IDs und technische Keys.
- Filename-Metadata bleibt privacy-schonend, weil keine Datei-Inhalte analysiert werden.

## Konsequenzen
- Bessere Filterbarkeit in Knowledge-Workflows
- Stabilere Scanner-Läufe bei großen/heterogenen Ordnern
- Vorbereitung auf spätere Tag-Nutzung in weiteren Domänen
