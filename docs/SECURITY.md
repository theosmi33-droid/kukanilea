# Security Notes

## Session Management

KUKANILEA erzwingt Session-Timeouts serverseitig:

- Idle-Timeout: Standard 60 Minuten Inaktivitaet, pro User konfigurierbar (15 bis 480 Minuten).
- Absolute Session-Lifetime: maximal 8 Stunden.
- Session-Checks laufen im `before_request`-Pfad und gelten damit fuer Web- und API-Anfragen (ausser explizit oeffentliche Routen).

Konfigurierbar ueber:

- `KUKANILEA_SESSION_ABSOLUTE_TIMEOUT_HOURS`
- `KUKANILEA_IDLE_TIMEOUT_DEFAULT_MINUTES`
- `KUKANILEA_IDLE_TIMEOUT_MIN_MINUTES`
- `KUKANILEA_IDLE_TIMEOUT_MAX_MINUTES`
- `KUKANILEA_IDLE_TOUCH_SECONDS`

Referenzen:

- OWASP Session Management Cheat Sheet
- OWASP ASVS / Broken Access Control Prinzipien (serverseitige Erzwingung)
