# 0006 - Phase 4 CRM Core + Offline EML Import

## Kontext
Phase 4 ergänzt einen tenant-sicheren CRM-Kern ohne neue externe Abhängigkeiten und ohne UI-Ausbau.

## Entscheidung
- Neue tenant-scoped Tabellen: `customers`, `contacts`, `deals`, `quotes`, `quote_items`, `emails_cache`.
- Alle Mutationen erzeugen Eventlog-Einträge über `event_append(...)`.
- E-Mail-Import ist offline-first via `.eml` (stdlib `email` Parser), ohne IMAP/Netzwerk.
- API-Endpunkte in `app/web.py` nutzen den bestehenden Tenant-Kontext und globale READ_ONLY-Sperre.
- KI-gestützte Sales-Vorschläge bleiben per `KUKA_AI_ENABLE=1` gated; default leer.

## Auswirkungen
- Tenant-Isolation ist testbar und abgesichert.
- Angebotserstellung aus Deal nutzt vorhandene Zeitdaten (projektbezogen), falls verfügbar.
- Defekte `.eml` werden robust gespeichert (raw BLOB), ohne Import-Abbruch.
