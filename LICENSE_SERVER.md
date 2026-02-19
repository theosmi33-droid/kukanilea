# License Server

See `/license_server/README.md` for setup, API and integration details.

## Scope in Phase 5

- Provides online validation endpoint compatible with `app/license.py`
- Supports revoke/expire/device checks
- Keeps runtime behavior fail-closed + grace in the main app

## Out of Scope

- Billing/checkout
- Multi-region deployment
- Complex admin UI
