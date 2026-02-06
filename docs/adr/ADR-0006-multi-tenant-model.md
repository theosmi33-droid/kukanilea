# ADR-0006: Multi-tenant data model

## Status
Accepted

## Context
KUKANILEA must guarantee tenant isolation for data access and filesystem operations. Tenant identifiers are never editable in the UI.

## Decision
- Every row in core tables includes `tenant_id` and is filtered by tenant for read/write.
- Filesystem operations resolve to per-tenant roots and are validated against allowlists.
- Auth memberships bind users to a tenant and role; tenant selection is not user-editable.

## Consequences
- All queries and tool actions must include tenant filters.
- Tests must validate tenant isolation and deny-by-default behavior.

## Alternatives Considered
- Single-tenant DB without tenant_id (rejected: cannot scale to multiple tenants).
