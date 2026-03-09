# Calendar Tenant Binding Policy

Date: 2026-03-08

- Calendar tools must execute only within active session tenant.
- Tenant identifiers from request payload must not override session tenant.
- Unknown tenant context must fail closed.

