# Lead Intake Inbox

Die Lead Intake Inbox erfasst eingehende Anfragen offline-first und tenant-sicher.

## Scope
- Tabellen: `leads`, `call_logs`, `appointment_requests`
- Timeline aus Eventlog + Facts (`call_logs`, `appointment_requests`)
- Quellen: `call`, `email`, `webform`, `manual`
- Status: `new`, `contacted`, `qualified`, `lost`, `won`

## Endpunkte
- UI:
  - `GET /leads/inbox`
  - `GET /leads/new`
  - `GET /leads/<id>`
  - Partials: `/leads/_table`, `/leads/_timeline/<lead_id>`, `/leads/_status/<lead_id>`
- JSON API:
  - `GET /api/leads`
  - `POST /api/leads`
  - `GET /api/leads/<id>`
  - `PUT /api/leads/<id>/status`
  - `POST /api/leads/<id>/note`
  - `POST /api/call-logs`
  - `POST /api/appointment-requests`
  - `PUT /api/appointment-requests/<id>/status`
  - `GET /api/appointment-requests/<id>/ics`

## PII-Regeln im Eventlog
Event-Payloads enthalten keine freien Texte oder Kontaktdaten wie E-Mail, Telefon, Message, Notes.
Erlaubt sind nur technische Metadaten (IDs, Status, Quelle, Timestamps, Tenant-ID).

## READ_ONLY
Bei `READ_ONLY=true` blockieren mutierende Routen mit `403` und `error_code=read_only`.
Die UI zeigt Banner und deaktivierte Controls.
