# ADR 0024 — Omni Assist v0: Conversation Hub (Email Sim)

- Status: Accepted
- Datum: 2026-02-16

## Kontext
KUKANILEA benötigt ein kanalunabhängiges Conversation-Modell als Basis für spätere Assistenz- und Agent-Funktionen.  
V0 soll offline-first, tenant-isoliert und sicher gegen PII-Leaks sein.

## Entscheidung
- Einführung einer append-or-ignore Tabelle `conversation_events` als zentrale Event-Wahrheit.
- Persistenz nur von redigiertem Payload (`redacted_payload_json`), nie von Raw-Input.
- Header-PII wird tokenisiert statt im Klartext gespeichert:
  - `from_domain`, `to_domains[]`, `from_token`, `to_tokens[]`.
- Idempotenz via zwei dedizierte Constraints:
  - `channel_ref_norm` (Message-ID normalisiert)
  - `audit_hash` (kanonischer redigierter Payload + Tenant)
- v0 Channel-Scope: nur `email` als Adapter (`email_sim`), aber Datenmodell unterstützt `chat`/`phone`.
- Operator-UI read-only (`/conversations`, `/conversations/<id>`).
- Deterministischer QA-Runner (`conversation_scenarios`) als Merge-Gate für Redaction/Isolation.

## Konsequenzen
- Debuggability erfolgt über strukturierte Metadaten + Audit-Hash statt Raw-Payload-Speicherung.
- Echte Kanaladapter (Chat/Phone) können additiv angebunden werden, ohne Schema-Bruch.
- Spätere Workflow-States sollten separat modelliert werden (`conversation_event_state`), um Events append-only zu halten.

