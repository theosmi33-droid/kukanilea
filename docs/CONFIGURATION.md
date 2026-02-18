# Configuration

Stand: 2026-02-18

## Automation Builder

### `WEBHOOK_ALLOWED_DOMAINS`
- Typ: String (komma-getrennte Domainliste)
- Zweck: Allowlist fuer Automation-Action `webhook`
- Standard: leer (`""`) => Webhooks sind fail-closed deaktiviert
- Beispiel:

```bash
WEBHOOK_ALLOWED_DOMAINS=hooks.example.com,api.partner.tld
```

Regeln:
- Nur exakte Domain-Matches (keine impliziten Wildcards/Subdomains)
- Nur `https://` URLs sind erlaubt
- `localhost` und IP-Adressen sind blockiert

## Lizenzvalidierung (optional, Offline-first mit Grace)

### `KUKANILEA_LICENSE_VALIDATE_URL`
- Typ: String (HTTPS URL)
- Zweck: Optionaler Online-Validierungsendpoint fuer signierte Lizenzen
- Standard: leer (`""`) => rein lokale Lizenzpruefung

### `KUKANILEA_LICENSE_VALIDATE_TIMEOUT_SECONDS`
- Typ: Integer
- Standard: `10`
- Zweck: Timeout fuer Online-Validierung

### `KUKANILEA_LICENSE_VALIDATE_INTERVAL_DAYS`
- Typ: Integer
- Standard: `30`
- Zweck: Nach wie vielen Tagen erneut online validiert wird

### `KUKANILEA_LICENSE_GRACE_DAYS`
- Typ: Integer
- Standard: `30`
- Zweck: Offline-Gnadenfrist, wenn Online-Validierung nicht erreichbar ist

### `KUKANILEA_LICENSE_CACHE_PATH`
- Typ: Pfad
- Standard: `~/Library/Application Support/KUKANILEA/license_cache.json`
- Zweck: Lokaler Cache fuer letzte erfolgreiche Validierung/Grace-Status
