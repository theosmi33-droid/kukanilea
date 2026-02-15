# Autonomy Phase 2a: Excludes, Global Tags, Filename Metadata

## Ziel
Phase 2a erweitert den lokalen Source-Scanner um:
- Exclude-Globs zur Scanner-Hygiene
- Globales Tag-System (tenant-sicher, wiederverwendbar)
- Metadaten aus Dateiname/Pfad ohne Inhaltsanalyse

## Excludes
`source_watch_config.exclude_globs` enthält optional ein JSON-Array mit Glob-Patterns.
Ungültige Werte fallen fail-safe auf Default-Patterns zurück.

Default:
- `**/.git/**`
- `**/__pycache__/**`
- `**/*.tmp`
- `**/*.part`
- `**/*.swp`
- `**/.DS_Store`

Matching erfolgt deterministisch mit `pathlib.Path(rel_path).match(pattern)`.

## Tags
Neue Tabellen:
- `tags`
- `tag_assignments`

Eigenschaften:
- Tenant-scope über `tenant_id`
- `name_norm` (casefold) verhindert Case-Duplikate
- Assignment-Allowlist in v0 nur für `knowledge_chunk`
- READ_ONLY blockiert alle Mutationen

## Eventlog-Härtung
Tag-Events enthalten bewusst keine Tag-Namen, um PII-Leaks zu vermeiden.
Nur IDs und technische Metadaten werden protokolliert.

## Filename-Metadata
Extraktion ausschließlich aus Dateiname/Pfad, nicht aus Inhalt.

Allowlist-Felder:
- `date_iso`
- `doctype`
- `customer_token` (nur strenges Token-Muster)
- `hints`

Metadaten werden in `source_files.metadata_json` gespeichert (max. 1024 Bytes).

## Grenzen
- Kein OCR in Phase 2a
- Keine Inhaltsklassifizierung
- Kein Netzwerkzugriff
