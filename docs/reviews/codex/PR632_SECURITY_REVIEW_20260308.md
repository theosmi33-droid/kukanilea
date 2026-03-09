# PR632 Security Review (2026-03-08)

## Scope
- Legacy task move operations are constrained to active tenant context.

## Risk Addressed
- Prevents cross-tenant task movement via legacy path.

## Verification Focus
- Tenant boundary remains enforced in task move API.
- Out-of-tenant move attempts are rejected.
