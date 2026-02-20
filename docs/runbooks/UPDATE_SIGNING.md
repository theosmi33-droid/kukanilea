# Update Signing Runbook

## Ziel
Installierbare Updates werden nur aus einem signierten Manifest akzeptiert.

## Manifest-Format (JSON)

```json
{
  "version": "1.0.0-beta.3",
  "release_url": "https://github.com/theosmi33-droid/kukanilea/releases/tag/v1.0.0-beta.3",
  "generated_at": "2026-02-20T22:00:00Z",
  "assets": [
    {
      "name": "KUKANILEA-1.0.0-beta.3-macos.zip",
      "platform": "darwin",
      "url": "https://github.com/.../KUKANILEA-1.0.0-beta.3-macos.zip",
      "sha256": "..."
    }
  ],
  "signatures": [
    {
      "alg": "ed25519",
      "key_id": "release-main",
      "sig": "<base64-or-base64url-signature>"
    }
  ]
}
```

## App-Konfiguration

- `KUKANILEA_UPDATE_MANIFEST_URL`: Manifest-URL
- `KUKANILEA_UPDATE_SIGNING_REQUIRED=1`: Signatur zwingend
- `KUKANILEA_UPDATE_SIGNING_PUBLIC_KEY_FILE`: Pfad zum PEM-Public-Key

## Verhalten

- Signatur ungültig oder fehlend und `KUKANILEA_UPDATE_SIGNING_REQUIRED=1`:
  - Update wird blockiert (fail-closed).
- Manifest nicht erreichbar und `KUKANILEA_UPDATE_SIGNING_REQUIRED=0`:
  - Fallback auf Release-API.

## Empfehlung

Für produktive Installationen immer:

```bash
export KUKANILEA_UPDATE_SIGNING_REQUIRED=1
```
