# Tenant Modell (Single-Tenant Lock)

Stand: 2026-02-20

## Ziel

Jede Kundeninstallation ist genau einem Tenant zugeordnet. Der Tenant-Kontext wird serverseitig gesetzt und nicht aus Client-Eingaben (Session-Override, Query, Header) vertraut.

## Quelle des Tenants

Beim Start wird `tenant_config` in der Core-DB sichergestellt (`id='fixed'`):

- `tenant_id`: stabile Tenant-ID fuer diese Installation
- `tenant_name`: Anzeigename/Branding

Reihenfolge fuer Initialwerte:

1. Lizenz-Payload (`tenant_id`, `tenant_name`/`company`)
2. Env-Fallback (`KUKANILEA_FIXED_TENANT_ID`, `KUKANILEA_TENANT_NAME`)
3. App-Fallback (`TENANT_DEFAULT`)

Ohne gueltige Tenant-ID startet die App nicht korrekt (fail-closed).

## Request-Verhalten

- In `before_request` wird der Tenant-Kontext in `g.tenant_ctx` gesetzt.
- Session-Tenant wird auf den festen Tenant ueberschrieben.
- Geschuetzte Endpoints ohne Tenant-Konfiguration liefern `403`.

## Zugriffsschutz

- Ressourcenzugriffe muessen tenant-gescoped erfolgen (z. B. `WHERE tenant_id=? AND id=?`).
- Clientseitige Tenant-Werte werden nicht als Autorisierungsgrundlage verwendet.

## DEV-Override

- Route: `/dev/tenant`
- Nur fuer Rolle `DEV` und nur von `localhost`.
- Es darf nur `tenant_name` geaendert werden.
- `tenant_id` bleibt unveraenderlich (read-only).
