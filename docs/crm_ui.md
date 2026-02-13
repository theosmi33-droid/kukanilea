# CRM UI (HTMX-first)

## Überblick
Neue CRM-Arbeitsoberfläche unter `/crm`:
- `/crm/customers` -> Kundenliste + Suche + Anlage
- `/crm/customers/<id>` -> Kunde mit Tabs (Contacts/Deals/Quotes/Emails)
- `/crm/deals` -> Deal-Pipeline nach Stage
- `/crm/quotes` -> Angebotsliste
- `/crm/quotes/<id>` -> Angebotsdetail + Positionen
- `/crm/emails/import` -> `.eml` Upload + letzte Imports

## Daily Flow
1. Kunde anlegen (`/crm/customers`)
2. Deal anlegen (`/crm/deals`)
3. Angebot aus Deal erstellen (`/api/quotes/from-deal/<deal_id>` oder UI-Flows)
4. `.eml` importieren (`/crm/emails/import`)

## PWA Installation
- Manifest: `/app.webmanifest`
- Service Worker: `/sw.js`

### Android
- Seite in Chrome öffnen
- "Zum Startbildschirm hinzufügen"

### iOS
- Seite in Safari öffnen
- Teilen -> "Zum Home-Bildschirm"

### Desktop
- In Chromium-basierten Browsern "Install app" verwenden

## Read-only Verhalten
Wenn `READ_ONLY=True`:
- Schreibaktionen serverseitig blockiert (bestehende Enforcement-Logik)
- UI zeigt Hinweisbanner
- Formulare/Buttons werden deaktiviert gerendert

## Lokal starten
```bash
python kukanilea_app.py
```

## Health
- Live: `/api/health/live`
- Ready: `/api/health/ready`

Die UI zeigt in der Topbar den Zustand (Live/Ready) über periodische Polls.
