# Admin: Floating Widget aktivieren

## Voraussetzungen
- Anwendung laeuft mit dem Standard-Layout `app/templates/layout.html`.
- Endpoint `/api/chat/compact` ist erreichbar.

## Technische Einbindung
- Globales Include: `app/templates/partials/floating_chat.html`
- Frontend: `app/static/js/chatbot.js`
- Styling: `app/static/css/components.css` + `app/static/css/haptic.css`

## Verify
1. Login als DEV/ADMIN.
2. Irgendeine Seite oeffnen (z. B. `/dashboard`).
3. `KI`-Button unten rechts sichtbar.
4. Klick oeffnet Overlay, `ESC` schliesst Overlay.
5. Schreibende Anfrage erzeugt Confirm-Gate.

## API-Vertrag
- `POST /api/chat/compact`
  - Input: `message`, `current_context`, `weak_hw`, `offline`
  - Output: `text`, `actions`, `requires_confirm`, `pending_id`, `thinking_steps`, `latency_ms`
- `GET /api/chat/compact?history=1`
  - Liefert tenant-/userbezogenen Widget-Verlauf.
