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

## Externe Ressourcen

KUKANILEA verwendet keine extern gehosteten Google Fonts.
Alle Schriften werden lokal aus `static/fonts/` ausgeliefert.

Zusatzschutz:

- Content Security Policy erzwingt `font-src 'self'`.
- Browser blockieren dadurch jeden externen Font-Nachladeversuch.
- Runtime-Assets enthalten keine Referenzen auf `fonts.googleapis.com` oder `fonts.gstatic.com`.

## LLM Tool-Use Security

Der lokale KI-Orchestrator erzwingt serverseitige Schutzmechanismen gegen Prompt-Injection:

- Tool-Allowlist: nur freigegebene Tool-Namen werden akzeptiert.
- Strikte Argumentvalidierung (`extra=\"forbid\"`): unbekannte/zusätzliche Felder werden verworfen.
- Confirm-Gate für mutierende Tools: Schreibaktionen werden erst nach expliziter serverseitig verifizierter Bestätigung ausgeführt.
- Replay-Schutz für Bestätigungstoken (einmalige Verwendung).
- Audit-Events für Tool-Calls (`ai_tool_call`) mit redigierten Argumenten.

Damit gilt: deny-by-default bei Tool-Aufrufen, keine stillen Mutationen durch Modell-Ausgaben.
