# ADR-0001: DB-first source of truth with strict tenancy

## Status
Accepted

## Context
KUKANILEA must be local-first, deterministic, and tenant scoped. Filesystem operations are executors, not sources of truth.

## Decision
- The database is the sole source of truth for documents, tasks, and audit trails.
- All data access is tenant scoped. Tenant identifiers are never editable in the UI.
- Filesystem operations (indexing, file open) are driven by DB state and tenant allowlists.

## Consequences
- All agents and APIs must include tenant_id in queries.
- Any filesystem action without a DB record is treated as a failure and audited.

## Alternatives Considered
- Filesystem-first with DB as cache (rejected: violates auditability and deterministic behavior).
