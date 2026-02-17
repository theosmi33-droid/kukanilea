# Email Connectors

## Feature Flags
- `EMAIL_ENABLED` (default: false)
- `IMAP_SMTP` (default: false)
- `GMAIL_OAUTH` (default: false)
- `MS_GRAPH` (default: false)

## IMAP v0 (current supported path)
Use IMAP for inbox listing in the local mailbox UI.

Security baseline:
- TLS only: `imaplib.IMAP4_SSL` with `ssl.create_default_context()`.
- Stored mailbox secrets are encrypted at rest.
- Set `EMAIL_ENCRYPTION_KEY` to enable password persistence.
- Without `EMAIL_ENCRYPTION_KEY`, users can still sync by entering the password per run.

Notes:
- No cleartext password persistence in DB.
- No PII payloads in eventlog.
- SMTP send path is not required for OCR/ops readiness.

## Gmail OAuth (Optional)
- Requires `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`.
- OAuth tokens stored per user (encrypted-at-rest placeholder).

## Microsoft Graph (Optional)
- Placeholder for future integration.
