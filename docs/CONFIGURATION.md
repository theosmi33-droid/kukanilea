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
