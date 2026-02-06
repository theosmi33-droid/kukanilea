# Secrets Handling

## Principles
- Keep secrets out of git history; use `.env` or OS keychain where possible.
- Local-first defaults must work without external credentials.
- Rotate secrets regularly and store least-privilege tokens only.

## Local Development
1. Copy `.env.example` to `.env` and update values.
2. Never commit `.env` files.

## Production Guidance
- Use a secrets manager (e.g., OS keychain or enterprise secret store).
- Restrict access to connector credentials and audit all changes.
- Use per-tenant credentials where applicable.
