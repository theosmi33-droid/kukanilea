# ADR-0007: Time Tracking as Tenant-Scoped Core Tables

## Status
Accepted

## Context
Phase 2 introduces time tracking as a must-have workflow. The system must be local-first, DB-first, and tenant-isolated with deterministic exports and audited actions. We also need to enforce “one running timer per user” safely under concurrent requests.

## Decision
Add `time_projects` and `time_entries` tables to the core DB with `tenant_id` on every row. Enforce a single running timer per user via a partial unique index on `(tenant_id, user)` where `end_at IS NULL`. Provide core functions for start/stop/edit/list/export and require audit logging for all mutations.

## Consequences
- **Positive**: Strong tenant isolation, deterministic exports, and concurrency-safe timers.
- **Negative**: Adds schema complexity and requires careful migrations when upgrading existing DBs.

## Alternatives Considered
- Store time data in filesystem logs — rejected (DB must be source of truth).
- Enforce running timer only in application logic — rejected (race-prone without DB constraint).
