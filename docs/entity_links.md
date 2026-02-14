# Entity Links v0

Entity Links v0 ist ein universeller, tenant-sicherer Verknüpfungs-Layer für Entitäten.

## Ziele
- Symmetrische Duplikate vermeiden (canonical ordering)
- Keine PII in Eventlog-Payloads
- READ_ONLY-respektierende Mutationen

## Schema
- `entity_links`
  - `id`, `tenant_id`
  - `a_type`, `a_id`, `b_type`, `b_id`
  - `link_type`, `created_at`, `updated_at`
  - `UNIQUE(tenant_id, a_type, a_id, b_type, b_id, link_type)`

## Canonical ordering
Beim Schreiben wird `(left_type,left_id,right_type,right_id)` deterministisch sortiert.
Dadurch sind `A->B` und `B->A` identisch und können nicht doppelt gespeichert werden.

## API/HTMX
- `GET /entity-links/<entity_type>/<entity_id>`
- `POST /entity-links/create`
- `POST /entity-links/<link_id>/delete`

## Sicherheit
- Type/Link-Type Allowlist
- Tenant-Filter in jeder Query
- Keine Titelauflösung aus Fremdentitäten (nur type + short id)
- Eventlog ohne E-Mail/Phone/Body/Notes-Felder
