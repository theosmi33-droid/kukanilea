# Knowledge ICS Source v0

## Scope
- Upload-only `.ics` ingestion (offline-first, no network).
- Policy-gated via `knowledge_source_policies.allow_calendar` and `allow_customer_pii`.
- Ingests only `VEVENT` fields:
  - `DTSTART`
  - `DTEND`
  - `SUMMARY`
  - `LOCATION`

## Security defaults
- Default deny (`allow_calendar=0`).
- No raw ICS storage.
- Ignored keys: `ATTENDEE`, `ORGANIZER`, `DESCRIPTION`, `COMMENT`, `CONTACT`, `ATTACH`, `URL`, `RRULE`.
- Hard limits:
  - upload size (`KNOWLEDGE_ICS_MAX_BYTES`, default 256 KB)
  - max parsed events (10)
  - max written chunks (50)
  - max unfolded line length (2000)

## Parser behavior
- Decodes with `utf-8` (`errors='replace'`).
- Performs RFC-style line unfolding before parsing.
- Handles datetime inputs:
  - `YYYYMMDD`
  - `YYYYMMDDTHHMMSS`
  - `YYYYMMDDTHHMMSSZ`
- Unsupported/invalid datetime values are dropped.

## Storage
- `knowledge_ics_sources`: metadata + dedup (`tenant_id`, `content_sha256`).
- `knowledge_ics_ingest_log`: status/reason per ingest.
- Redacted output is persisted to `knowledge_chunks` (`source_type='calendar'`) and indexed in FTS.

## Events
- `knowledge_ics_ingested` (PII-free payload only):
  - source id
  - sha256 prefix
  - parsed event count
  - chunk count
  - filename presence flag
