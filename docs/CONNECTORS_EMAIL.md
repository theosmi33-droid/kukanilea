# Email Connectors

## Security Baseline
- TLS only: `IMAP4_SSL` / `SMTP_SSL` or `STARTTLS` with `ssl.create_default_context()`.
- No cleartext mailbox credentials or OAuth tokens in the database.
- `EMAIL_ENCRYPTION_KEY` is mandatory for account secrets and OAuth token storage.
- Fail-closed behavior:
  - missing `EMAIL_ENCRYPTION_KEY` => no mailbox sync, no send, no OAuth token persistence.
  - missing OAuth client config => OAuth connect is blocked.
- Eventlog payloads contain only IDs/metrics (no PII bodies/subjects/emails).

## Provider Auth Matrix
| Provider | Inbound | Outbound | Auth mode in KUKANILEA | Notes |
| --- | --- | --- | --- | --- |
| Generic IMAP/SMTP | IMAP4_SSL | SMTP_SSL/STARTTLS | `password` | Legacy-compatible mode. |
| Google Workspace / Gmail | IMAP XOAUTH2 | SMTP XOAUTH2 | `oauth_google` | Recommended for modern setups. |
| Microsoft 365 / Exchange Online | IMAP OAuth2 | SMTP OAuth2 | `oauth_microsoft` | Recommended for modern setups. |

## Required Configuration
- Google OAuth:
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
- Microsoft OAuth:
  - `MICROSOFT_CLIENT_ID`
  - `MICROSOFT_CLIENT_SECRET`
- Optional redirect base:
  - `OAUTH_REDIRECT_BASE` (if not set, host URL is used)

## Runtime Behavior
- Postfach account stores auth mode (`password`, `oauth_google`, `oauth_microsoft`).
- OAuth connect flow:
  1. User starts connect.
  2. App creates `state` + PKCE verifier/challenge.
  3. Callback validates `state` with `hmac.compare_digest`.
  4. Tokens are exchanged and encrypted at rest.
- Sync report fields per account:
  - `last_sync_at`
  - `last_sync_status`
  - `last_sync_error`
  - `last_sync_imported`
  - `last_sync_duplicates`

## Troubleshooting
- `oauth_client_not_configured`:
  - Check provider client ID/secret env vars.
- `oauth_token_missing`:
  - Re-run OAuth connect for account.
- `oauth_refresh_failed`:
  - Re-consent account and ensure refresh token/scope is valid.
- `email_encryption_key_missing`:
  - Set `EMAIL_ENCRYPTION_KEY` and restart app.
- `imap_sync_failed` / `smtp_send_failed`:
  - Verify host/port/TLS settings and provider-side permissions.
