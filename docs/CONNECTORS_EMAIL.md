# Email Connectors

## Feature Flags
- `EMAIL_ENABLED` (default: false)
- `IMAP_SMTP` (default: false)
- `GMAIL_OAUTH` (default: false)
- `MS_GRAPH` (default: false)

## IMAP/SMTP (Baseline)
Use IMAP for inbox listing and SMTP for sending.

**Required env**
- `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_PASSWORD`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`

## Gmail OAuth (Optional)
- Requires `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`.
- OAuth tokens stored per user (encrypted-at-rest placeholder).

## Microsoft Graph (Optional)
- Placeholder for future integration.
