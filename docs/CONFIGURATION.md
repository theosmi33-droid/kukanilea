# Configuration

Stand: 2026-02-19

## Postfach / E-Mail Secrets

### `EMAIL_ENCRYPTION_KEY` (pflichtig fuer Postfach)
- Typ: String
- Zweck: Schluesselmaterial fuer at-rest Verschluesselung von Postfach-Credentials
  und OAuth-Tokens.
- Standard: leer (`""`) => Postfach-Funktionen laufen fail-closed nicht.

Hinweise:
- Bereits gespeicherte Legacy-Secrets werden beim Zugriff automatisch auf
  AES-GCM migriert, wenn `EMAIL_ENCRYPTION_KEY` gesetzt ist.
- Ohne Key sind IMAP/SMTP-Operationen und OAuth-Token-Nutzung deaktiviert.

Generieren:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Setzen (Shell):

```bash
export EMAIL_ENCRYPTION_KEY="dein-schluessel"
```

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
- Alias: `LICENSE_SERVER_URL` (wird genutzt, falls `KUKANILEA_LICENSE_VALIDATE_URL` leer ist)
- Test/CI: fuer deterministische Tests lokale Stub-URL nutzen (z. B. `http://127.0.0.1:11436/api/v1/validate`)

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

### `KUKANILEA_LICENSE_PATH`
- Typ: Pfad
- Standard: `~/Library/Application Support/KUKANILEA/license.json`
- Zweck: Speicherort der signierten Lizenzdatei (wird ueber `/license` geschrieben)

## Tenant Lock (Single-Tenant)

### `KUKANILEA_FIXED_TENANT_ID`
- Typ: String
- Standard: `KUKANILEA` (ueber `TENANT_DEFAULT`, falls gesetzt)
- Zweck: Fallback fuer feste Tenant-ID pro Installation (wenn Lizenzpayload keine Tenant-ID liefert)

### `KUKANILEA_TENANT_NAME`
- Typ: String
- Standard: Wert von `KUKANILEA_FIXED_TENANT_ID`
- Zweck: Fallback fuer Tenant-Anzeigenamen/Branding

Hinweis:
- Tenant-Kontext wird serverseitig aus `tenant_config` erzwungen.
- Clientseitige Tenant-Werte (Session/Request) werden fuer Autorisierung nicht vertraut.

## RBAC / Berechtigungen

- Rollen und Permissions werden in der Auth-DB gespeichert (`auth_roles`, `auth_permissions`, `auth_role_permissions`, `auth_user_roles`).
- Berechtigungen werden serverseitig erzwungen (deny-by-default).
- Verwaltung erfolgt im UI unter `/settings/permissions` (nur Owner Admin / DEV).
- Legacy-Rollen werden automatisch auf RBAC-Rollen gemappt.

## Lokale KI (Ollama)

### `OLLAMA_BASE_URL`
- Typ: String (URL)
- Standard: `http://127.0.0.1:11434`
- Zweck: Basis-URL fuer lokalen Ollama-Dienst

### `OLLAMA_MODEL`
- Typ: String
- Standard: `llama3.1:8b`
- Zweck: Standardmodell fuer AI-Chat und Orchestrator

### `OLLAMA_TIMEOUT`
- Typ: Integer (Sekunden)
- Standard: `300`
- Zweck: Request-Timeout fuer lokale LLM-Generierung

## Update-Checker (notify-only)

### `KUKANILEA_UPDATE_CHECK_ENABLED`
- Typ: Bool (`0|1`)
- Standard: `0` (deaktiviert)
- Zweck: Aktiviert die Hinweis-Pruefung auf neuere Releases im Settings-Bereich

### `KUKANILEA_UPDATE_CHECK_URL`
- Typ: String (URL)
- Standard: `https://api.github.com/repos/theosmi33-droid/kukanilea/releases/latest`
- Zweck: Endpoint fuer Release-Metadaten

### `KUKANILEA_UPDATE_CHECK_TIMEOUT_SECONDS`
- Typ: Integer
- Standard: `5`
- Zweck: Timeout fuer Update-Check-Requests

### `KUKANILEA_UPDATE_INSTALL_ENABLED`
- Typ: Bool (`0|1`)
- Standard: `0` (deaktiviert)
- Zweck: Aktiviert den DEV In-Place-Install-Flow (`/dev/update`)

### `KUKANILEA_UPDATE_INSTALL_URL`
- Typ: String (URL)
- Standard: Wert von `KUKANILEA_UPDATE_CHECK_URL`
- Zweck: Release-Endpoint fuer installierbare Update-Assets

### `KUKANILEA_UPDATE_INSTALL_TIMEOUT_SECONDS`
- Typ: Integer
- Standard: `30`
- Zweck: Timeout fuer Download/Metadaten im Install-Flow

### `KUKANILEA_UPDATE_MANIFEST_URL`
- Typ: String (URL)
- Standard: leer (`""`)
- Zweck: Optionaler Endpoint fuer ein signiertes Update-Manifest (bevorzugte Quelle fuer installierbare Assets)

### `KUKANILEA_UPDATE_SIGNING_REQUIRED`
- Typ: Bool (`0|1`)
- Standard: `0`
- Zweck: Erzwingt gueltige Manifest-Signaturpruefung (fail-closed bei Signatur-/Fetch-Fehlern)

### `KUKANILEA_UPDATE_SIGNING_PUBLIC_KEY`
- Typ: String (PEM oder Base64-kodiertes PEM)
- Standard: leer (`""`)
- Zweck: Oeffentlicher Schluessel zur Signaturpruefung des Update-Manifests

### `KUKANILEA_UPDATE_SIGNING_PUBLIC_KEY_FILE`
- Typ: Pfad
- Standard: leer (`""`)
- Zweck: Alternative zu `KUKANILEA_UPDATE_SIGNING_PUBLIC_KEY`; wird aus Datei geladen

### `KUKANILEA_UPDATE_APP_DIR`
- Typ: Pfad
- Standard: automatisch erkannter App-Pfad
- Zweck: Installationsziel fuer Atomic-Swap-Updates

### `KUKANILEA_UPDATE_DOWNLOAD_DIR`
- Typ: Pfad
- Standard: `<KUKANILEA_USER_DATA_ROOT>/updates`
- Zweck: Ablagepfad fuer heruntergeladene Update-Archive

## Session Management

### `KUKANILEA_SESSION_ABSOLUTE_TIMEOUT_HOURS`
- Typ: Integer
- Standard: `8`
- Zweck: Absolute maximale Sitzungsdauer in Stunden (serverseitig erzwungen).

### `KUKANILEA_IDLE_TIMEOUT_DEFAULT_MINUTES`
- Typ: Integer
- Standard: `60`
- Zweck: Standard-Inaktivitaets-Timeout pro User in Minuten.

### `KUKANILEA_IDLE_TIMEOUT_MIN_MINUTES`
- Typ: Integer
- Standard: `15`
- Zweck: Untere Grenze fuer benutzerseitig einstellbares Inaktivitaets-Timeout.

### `KUKANILEA_IDLE_TIMEOUT_MAX_MINUTES`
- Typ: Integer
- Standard: `480`
- Zweck: Obere Grenze fuer benutzerseitig einstellbares Inaktivitaets-Timeout.

### `KUKANILEA_IDLE_TOUCH_SECONDS`
- Typ: Integer
- Standard: `60`
- Zweck: Aktualisiert `last_activity` maximal alle N Sekunden, um Session-Schreiblast zu begrenzen.

## Content Security Policy (CSP)

KUKANILEA sendet einen restriktiven CSP-Header fuer alle Responses:

```text
Content-Security-Policy: default-src 'self'; font-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'
```

Hinweise:

- `font-src 'self'` blockiert externe Schriftarten (z. B. Google Fonts) browserseitig.
- `style-src`/`script-src` enthalten `unsafe-inline`, da die aktuelle UI Inline-Styles/-Skripte nutzt.
- Externe CDN-Fonts sind nicht erlaubt; Schriften werden lokal unter `static/fonts/` ausgeliefert.

## Lizenzserver (separater Service)

Diese Variablen gelten nur fuer den separaten Server unter `license_server/`.

### `LICENSE_SERVER_DB`
- Typ: Pfad
- Standard: `license_server/license_server.db`
- Zweck: SQLite-Datei fuer Lizenzdaten

### `LICENSE_SERVER_PORT`
- Typ: Integer
- Standard: `5061`
- Zweck: HTTP-Port des Lizenzservers

### `LICENSE_SERVER_API_TOKEN`
- Typ: String
- Standard: leer (`""`)
- Zweck: Optionaler Schutz fuer Admin-Endpoint `/api/v1/licenses/upsert`

## Pilot / Demo Seed

### `KUKANILEA_ANONYMIZATION_KEY`
- Typ: String
- Zweck: Deterministische Anonymisierung fuer Source-Scan-Metadaten (z. B. gehashte Dateipfade).
- Standard: leer (`""`)
- Empfehlung: fuer Pilotbetrieb setzen, damit Scan-/Seed-Metadaten stabil und nachvollziehbar sind.

Beispiel:
```bash
export KUKANILEA_ANONYMIZATION_KEY="pilot-anon-key"
```

### Demo-Daten laden (CLI)
```bash
python scripts/seed_demo_data.py --tenant-name "DEMO AG"
```

Reset fuer reproduzierbaren Pilottest:
```bash
python scripts/seed_demo_data.py --tenant-name "DEMO AG" --force
```
