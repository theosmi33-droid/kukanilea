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

## UI-Praeferenzen (pro User, serverseitig)

- Theme (`light`/`dark`) und Sidebar-Minimierung werden pro User in der Auth-DB gespeichert (`auth_user_preferences`).
- Schreibend ueber:
  - `POST /settings/ui/theme` mit JSON `{"theme":"light|dark"}`
  - `POST /settings/ui/sidebar` mit JSON `{"collapsed": true|false}`
- Beim Rendern der App-Shell werden gespeicherte Werte als Server-Default geladen, lokale Browser-Preferences bleiben als schneller Client-Fallback aktiv.

## Lokale KI (Ollama)

### `OLLAMA_BASE_URL`
- Typ: String (URL)
- Standard: `http://127.0.0.1:11434`
- Zweck: Basis-URL fuer lokalen Ollama-Dienst

### `OLLAMA_MODEL`
- Typ: String
- Standard: `llama3.1:8b`
- Zweck: Standardmodell fuer AI-Chat und Orchestrator

### `KUKANILEA_OLLAMA_MODEL_FALLBACKS`
- Typ: CSV-Liste
- Standard: `llama3.2:3b,qwen2.5:3b`
- Zweck: Lokale Modell-Fallback-Kette, wenn das Primaermodell fehlt/fehlschlaegt.
- Beispiel:
```bash
export OLLAMA_MODEL="llama3.2:3b"
export KUKANILEA_OLLAMA_MODEL_FALLBACKS="llama3.1:8b,qwen2.5:3b"
```

### `OLLAMA_TIMEOUT`
- Typ: Integer (Sekunden)
- Standard: `300`
- Zweck: Request-Timeout fuer lokale LLM-Generierung

### `KUKANILEA_OLLAMA_AUTOSTART`
- Typ: Bool (`0|1`)
- Standard: `1`
- Zweck: Startet Ollama beim nativen KUKANILEA-Desktop-Start automatisch, wenn Ollama nicht erreichbar ist.

### `KUKANILEA_OLLAMA_AUTOSTART_TIMEOUT_SECONDS`
- Typ: Integer (Sekunden)
- Standard: `20`
- Zweck: Maximale Wartezeit auf Ollama nach Autostart.

### `KUKANILEA_AI_BOOTSTRAP_ON_FIRST_RUN`
- Typ: Bool (`0|1`)
- Standard: `1`
- Zweck: Startet beim ersten App-Run ein AI-Bootstrap (Ollama + Modell-Prefetch + Personal-Memory-Schema).

### `KUKANILEA_AI_BOOTSTRAP_PULL_MODELS`
- Typ: Bool (`0|1`)
- Standard: `1`
- Zweck: Zieht konfigurierte Modelle (`OLLAMA_MODEL` + Fallbacks) automatisch.

### `KUKANILEA_AI_BOOTSTRAP_MODEL_LIST`
- Typ: CSV-Liste
- Standard: leer (`""`)
- Zweck: Erzwingt eine konkrete Modellliste fuer Erstinstallation; ueberschreibt Default+Fallback.

### `KUKANILEA_AI_BOOTSTRAP_MODEL_PULL_TIMEOUT_SECONDS`
- Typ: Integer (Sekunden)
- Standard: `1800`
- Zweck: Timeout je Modell-Pull im Erstinstallations-Bootstrap.

### `KUKANILEA_AI_BOOTSTRAP_USE_MODELPACK`
- Typ: Bool (`0|1`)
- Standard: `1`
- Zweck: Nutzt optional ein lokales Offline-Modelpack (`.tar.gz`) im First-Install-Bootstrap.

### `KUKANILEA_AI_BOOTSTRAP_MODELPACK_FILE`
- Typ: Dateipfad
- Standard: `~/Library/Application Support/KUKANILEA/modelpacks/ollama-modelpack.tar.gz`
- Zweck: Pfad zu einem vorbereiteten Ollama-Modelpack fuer Offline-Installationen.

### `KUKANILEA_AI_BOOTSTRAP_MODELPACK_EXPORT_DIR`
- Typ: Verzeichnispfad
- Standard: `~/Library/Application Support/KUKANILEA/modelpacks`
- Zweck: Zielordner fuer exportierte Modelpacks (`POST /api/ai/modelpack/export`).

### `KUKANILEA_AI_BOOTSTRAP_STATE_FILE`
- Typ: Dateipfad
- Standard: `~/Library/Application Support/KUKANILEA/ai_bootstrap_state.json`
- Zweck: Persistenter Status des First-Install-Bootstraps (fuer Support/Diagnose).

### `KUKANILEA_AI_MEMORY_DB`
- Typ: Dateipfad
- Standard: `~/Library/Application Support/KUKANILEA/ai_memory.sqlite3`
- Zweck: Eigene lokale Personal-Memory-DB fuer benutzerindividuelle Assistenznotizen.

## KI-Provider-Router (robuste Assistenz)

### `KUKANILEA_AI_PROVIDER_ORDER`
- Typ: CSV-Liste
- Standard: `ollama`
- Zweck: Reihenfolge der Provider fuer Failover
- Erlaubte Werte:
  - `vllm`
  - `lmstudio`
  - `ollama`
  - `groq`
  - `anthropic`
  - `gemini`
  - `openai_compat`
  - `openai_compat_fallback`

Empfehlung:
```bash
export KUKANILEA_AI_PROVIDER_ORDER="vllm,lmstudio,ollama,groq"
```

### `KUKANILEA_AI_PROVIDERS_JSON`
- Typ: JSON-Array
- Standard: leer (`""`)
- Zweck: Vollstaendige Provider-Konfiguration inkl. Prioritaeten.
- Hinweis: Wenn gesetzt, hat diese Variable Vorrang vor `KUKANILEA_AI_PROVIDER_ORDER`.

### `KUKANILEA_AI_PROVIDER_RETRIES`
- Typ: Integer
- Standard: `1`
- Zweck: Anzahl Wiederholungen pro Provider vor Failover.

### `KUKANILEA_AI_HEALTH_TTL_SECONDS`
- Typ: Integer
- Standard: `30`
- Zweck: TTL fuer gecachte Health-Checks.

### `KUKANILEA_AI_PROVIDER_POLICY_JSON`
- Typ: JSON-Objekt
- Standard: leer (`""`)
- Zweck: Serverseitige Mandanten-/Rollen-Policy fuer erlaubte Provider.
- Beispiele fuer Keys:
  - `default`, `tenants`, `roles`, `tenant_roles`
  - Rule-Keys: `allow_providers`, `deny_providers`, `allow_local`, `allow_cloud`, `allowed_roles`, `blocked_roles`

### vLLM
- `KUKANILEA_VLLM_BASE_URL` (Standard `http://127.0.0.1:8000`)
- `KUKANILEA_VLLM_MODEL`
- `KUKANILEA_VLLM_API_KEY` (optional)
- `KUKANILEA_VLLM_TIMEOUT` (Standard `60`)

### LM Studio
- `KUKANILEA_LMSTUDIO_BASE_URL` (Standard `http://127.0.0.1:1234`)
- `KUKANILEA_LMSTUDIO_MODEL`
- `KUKANILEA_LMSTUDIO_TIMEOUT` (Standard `60`)

### Groq
- `KUKANILEA_GROQ_BASE_URL` (Standard `https://api.groq.com/openai/v1`)
- `KUKANILEA_GROQ_MODEL`
- `KUKANILEA_GROQ_API_KEY` oder `GROQ_API_KEY`
- `KUKANILEA_GROQ_TIMEOUT` (Standard `30`)

### Anthropic
- `KUKANILEA_ANTHROPIC_BASE_URL` (Standard `https://api.anthropic.com`)
- `KUKANILEA_ANTHROPIC_MODEL` (Standard `claude-3-5-sonnet-latest`)
- `KUKANILEA_ANTHROPIC_API_KEY` oder `ANTHROPIC_API_KEY`
- `KUKANILEA_ANTHROPIC_TIMEOUT` (Standard `60`)

### Gemini
- `KUKANILEA_GEMINI_BASE_URL` (Standard `https://generativelanguage.googleapis.com`)
- `KUKANILEA_GEMINI_MODEL` (Standard `gemini-1.5-flash`)
- `KUKANILEA_GEMINI_API_KEY` oder `GEMINI_API_KEY` oder `GOOGLE_API_KEY`
- `KUKANILEA_GEMINI_TIMEOUT` (Standard `60`)

### OpenAI-kompatibel (generisch)
- `KUKANILEA_OPENAI_COMPAT_BASE_URL`
- `KUKANILEA_OPENAI_COMPAT_MODEL`
- `KUKANILEA_OPENAI_COMPAT_API_KEY`
- `KUKANILEA_OPENAI_COMPAT_TIMEOUT`

Sekundaerer Fallback (optional):
- `KUKANILEA_OPENAI_COMPAT_BASE_URL_FALLBACK`
- `KUKANILEA_OPENAI_COMPAT_MODEL_FALLBACK`
- `KUKANILEA_OPENAI_COMPAT_API_KEY_FALLBACK`
- `KUKANILEA_OPENAI_COMPAT_TIMEOUT_FALLBACK`

## Externe Quellen (DB-test als read-only Source Root)

Fuer grosse Kundenordner (z. B. `~/Downloads/DB-test`) kann der Source-Scanner als read-only Quelle angebunden werden.
Die Originaldateien werden dabei nicht veraendert; KUKANILEA schreibt nur in eigene Index-/Log-Tabellen.

Beispiel:
```bash
python scripts/connect_source_root.py \
  --source-root "/Users/<user>/Downloads/DB-test" \
  --runs 3 \
  --budget-ms 25000
```

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
