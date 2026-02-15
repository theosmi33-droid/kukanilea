# Autonomy Phase 2b: Auto-Tagging, Tokens, Dedup

Dieses Paket erweitert den lokalen Source-Scanner um drei Funktionen:

1. Regelbasiertes Auto-Tagging fuer `knowledge_chunk`-Eintraege.
2. Token-Felder fuer Dokumenttyp und Korrespondenz (`doctype_token`, `correspondent_token`).
3. Dedup vor Ingest auf Basis von `sha256` + `size_bytes`.

## Ziele

- Offline-first, ohne neue Dependencies.
- Tenant-sichere Verarbeitung (`tenant_id` in allen Queries).
- READ_ONLY-Block fuer alle Mutationen.
- Eventlog ohne PII (keine Pfade, Dateinamen, Inhalte).

## Auto-Tagging Rules

- Tabelle: `auto_tagging_rules`
- Pro Tenant aktivierbare Regeln mit Prioritaet.
- Condition-DSL und Action-DSL sind streng allowlisted.
- JSON wird kanonisiert gespeichert (`sort_keys=True`).

### Conditions (v0)

- `filename_glob`
- `ext_in`
- `meta_token_in` (`doctype`, `correspondent`, `date`)
- `date_between`
- `tags_any`

### Actions (v0)

- `add_tag`
- `remove_tag`
- `set_doctype`
- `set_correspondent`

## Dedup

Vor dem Ingest wird fuer jede Datei `sha256` und `size_bytes` berechnet.
Wenn bereits eine kanonische Quelle mit gleichem Hash + Groesse und vorhandener `knowledge_chunk_id` existiert:

- kein erneuter Ingest
- `duplicate_of_file_id` wird gesetzt
- `source_ingest_log` erhaelt `dedupe_skip`
- Event `source_file_deduped` wird geschrieben

## Tokens

Scanner-Metadaten und Regeln koennen folgende Tokens setzen:

- `doctype_token` (z. B. `invoice`, `offer`)
- `correspondent_token` (z. B. `kd-123`, `supplier-42`)

Beide Felder sind auf ein sicheres Token-Format begrenzt (`[a-z0-9_-]{1,32}`).

## UI

Neue Admin-/Operator-Routen:

- `GET /autonomy/autotag/rules`
- `GET /autonomy/autotag/rules/new`
- `POST /autonomy/autotag/rules/create`
- `POST /autonomy/autotag/rules/<id>/toggle`
- `POST /autonomy/autotag/rules/<id>/delete`

Die UI baut JSON-DSL serverseitig aus allowlisted Formularfeldern. Es gibt keinen freien JSON-Editor in v0.

## Sicherheit

- Kein Netzwerk, kein Subprocess, kein dynamischer Code.
- Eventlog-Payloads enthalten nur IDs, Enums, Route-Keys.
- Keine unescaped HTML-Ausgabe (`|safe` wird nicht verwendet).
