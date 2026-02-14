# Lead Intake Inbox

Die Lead Intake Inbox erfasst eingehende Anfragen offline-first und tenant-sicher.

## Scope
- Tabellen: `leads`, `call_logs`, `appointment_requests`, `lead_blocklist`
- Timeline aus Eventlog + Facts (`call_logs`, `appointment_requests`)
- Quellen: `call`, `email`, `webform`, `manual`
- Status: `new`, `screening`, `contacted`, `qualified`, `lost`, `won`, `ignored`

## v2 Patterns
- Gatekeeper Queue: unbekannte Leads starten in `screening`.
- Priority + Pin: `priority` (`normal|high`) und `pinned` steuern Sortierung.
- Ownership + Due: `assigned_to` und `response_due` für Shared Inbox.

## Blocklist Verhalten
- `lead_blocklist` unterstützt `email|domain|phone` je Tenant.
- Treffer setzen Lead auf `ignored` mit `blocked_reason=blocklist:<kind>`.
- Der Lead wird trotzdem gespeichert (Audit-Nachweis), aber standardmäßig nicht in aktiven Inbox-Tabs priorisiert.

## Endpunkte
- UI:
  - `GET /leads/inbox`
  - `GET /leads/new`
  - `GET /leads/<id>`
  - Partials: `/leads/_table`, `/leads/_timeline/<lead_id>`, `/leads/_status/<lead_id>`
  - Actions: `/leads/<id>/screen/accept`, `/leads/<id>/screen/ignore`, `/leads/<id>/priority`, `/leads/<id>/assign`, `/leads/blocklist/add`
- JSON API:
  - `GET /api/leads`
  - `POST /api/leads`
  - `GET /api/leads/<id>`
  - `PUT /api/leads/<id>/status`
  - `POST /api/leads/<id>/screen/accept`
  - `POST /api/leads/<id>/screen/ignore`
  - `PUT /api/leads/<id>/priority`
  - `PUT /api/leads/<id>/assign`
  - `POST /api/leads/blocklist`
  - `POST /api/leads/<id>/note`
  - `POST /api/call-logs`
  - `POST /api/appointment-requests`
  - `PUT /api/appointment-requests/<id>/status`
  - `GET /api/appointment-requests/<id>/ics`

## PII-Regeln im Eventlog
Event-Payloads enthalten keine Freitext- oder Kontaktfelder (`contact_*`, `message`, `notes`, `caller_phone`, `description`).
Erlaubt sind technische Metadaten (IDs, Status, Quelle, Priorität, Due/Owner-Presence, Tenant-ID).

## READ_ONLY
Bei `READ_ONLY=true` blockieren mutierende Routen mit `403` und `error_code=read_only`.
Die UI zeigt Banner und deaktivierte Controls.
