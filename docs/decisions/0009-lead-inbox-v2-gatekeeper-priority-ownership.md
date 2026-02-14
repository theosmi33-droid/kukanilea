# 0009 - Lead Inbox v2: Gatekeeper, Priority, Ownership

## Kontext
Lead Intake v1 reduziert Verlust durch strukturierte Erfassung. Für operativen Alltag fehlen noch drei Muster:
- Gatekeeper-Screening für unbekannte Leads
- Priorisierung/Pinning
- Zuständigkeit + Antwort-Fälligkeit

## Entscheidung
- Additive Erweiterung des Lead-Schemas um `priority`, `pinned`, `assigned_to`, `response_due`, `screened_at`, `blocked_reason`.
- Neue Tabelle `lead_blocklist` je Tenant (`email|domain|phone`).
- Keine separate `lead_events` Tabelle; Eventlog bleibt Single Source für Audit.
- Eventlog `entity_id` bleibt INTEGER-kompatibel über deterministisches Mapping von Text-IDs.

## Sicherheitsregeln
- Offline-first, keine Netzwerkaufrufe im Lead-Module.
- Keine Codeausführung/Shell-Prozesse.
- Parametrisierte SQL-Queries.
- Eventlog-Payload ohne PII-Felder.
- Input-Limits vor DB-Write.
- ICS-Ausgabe CRLF-sicher mit sanitisierten Feldern.

## Konsequenzen
- Unbekannte Leads landen in `screening`, geblockte Absender in `ignored`.
- Inbox ist auf Abarbeitung optimiert: Pin/Prio, Owner, Due-Fokus.
- Bestehende Freeze-Invarianten (Lizenz/Pfade/Release/Eventlog-Schema) bleiben intakt.
