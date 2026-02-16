# Omni Assist v0 — Conversation Hub

## Ziel
- Einheitliches Event-Modell für kanalunabhängige Conversations.
- v0 startet mit `email` (Fixture/Offline-Ingest), `chat` und `phone` sind als Modellwerte vorbereitet.
- Persistenz speichert ausschließlich redigierte Nutzdaten.

## Datenmodell
Tabelle: `conversation_events`
- `tenant_id`: Mandatory Tenant-Isolation.
- `channel`: `email|chat|phone`.
- `channel_ref_norm`: normalisierte Dedupe-Referenz (z. B. `Message-ID`).
- `redacted_payload_json`: einzig persistierter Payload.
- `audit_hash`: SHA-256 über kanonischen Redacted-Payload + Tenant.

Dedupe:
- `UNIQUE(tenant_id, channel, channel_ref_norm)` wenn Referenz vorhanden.
- `UNIQUE(tenant_id, channel, audit_hash)` als Fallback.

## Redaction-Policy (v0)
- Keine vollständigen Mailadressen in der DB.
- Gespeichert werden:
  - `from_domain`
  - `to_domains[]`
  - `from_token` / `to_tokens[]` (`sha256(lower(address))`)
- `subject` und `body` laufen durch `knowledge_redact_text(...)` vor Persistenz.

## APIs (Core)
`app/omni/hub.py`:
- `ingest_fixture(...)`
- `store_event(...)`
- `list_events(...)`
- `get_event(...)`

## UI
- `/conversations`: read-only Übersicht.
- `/conversations/<id>`: Event-Detail mit redigiertem Payload.

## Invarianten
- Tenant-Filter in allen Queries.
- READ_ONLY blockiert Commit-Mutationen.
- Keine PII-Marker in `conversation_events.redacted_payload_json`.

