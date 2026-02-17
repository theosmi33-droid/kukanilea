# Secrets Handling

## Principles
- Keep secrets out of git history; use `.env` or OS keychain where possible.
- Local-first defaults must work without external credentials.
- Rotate secrets regularly and store least-privilege tokens only.

## Local Development
1. Copy `.env.example` to `.env` and update values.
2. Never commit `.env` files.
3. For local IMAP password persistence, set `EMAIL_ENCRYPTION_KEY`.
4. If `EMAIL_ENCRYPTION_KEY` is not set, IMAP sync still works with manual password entry per sync.

## Production Guidance
- Use a secrets manager (e.g., OS keychain or enterprise secret store).
- Restrict access to connector credentials and audit all changes.
- Use per-tenant credentials where applicable.
