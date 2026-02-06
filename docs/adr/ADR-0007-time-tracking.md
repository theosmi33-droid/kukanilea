# ADR-0007: Local-first time tracking

## Status
Accepted

## Context
Construction offices need simple time tracking tied to customers/projects. The system must remain offline-first and tenant-scoped.

## Decision
- Add `time_projects` and `time_entries` tables to the core DB with tenant scoping.
- Enforce one active timer per user per tenant.
- Provide APIs for start/stop, weekly view, and CSV export.

## Consequences
- Time tracking can be used without external services.
- CSV export enables downstream payroll/ERP workflows.

## Alternatives Considered
- SaaS time tracking integration (rejected: breaks local-first default).
