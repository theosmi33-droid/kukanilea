# Phase 2 — Product Core for Handwerk

## Why
Handwerk teams need deterministic, tenant-safe workflows that save time on-site and in the office. Phase 2 introduces work time tracking, a jobs/tasks core, and a hardened document intake pipeline while preserving local-first, DB-first guarantees.

## Scope
### 2.1 Work Time Tracking (PR #1)
- DB schema: `time_projects`, `time_entries`.
- Constraint: **1 running timer per user** enforced at DB + service layer.
- API: start/stop timer, list day/week, edit entry, approve entry, export CSV.
- UI: mobile-first timer, weekly overview, basic approvals.
- Tests: tenant isolation, concurrency/one-running-timer, CSV export determinism.

### 2.2 Jobs/Projects/Tasks Core (PR #2)
- Entities: project, job, task, status, assignees.
- API + UI to manage tasks and link to docs/customers/time entries.
- Deterministic reminders + due dates.

### 2.3 Document Intake → Review → Archive (Hardening)
- Upload/queue reliability improvements.
- Better indexing coverage + stable token open.
- End-to-end ingest tests.

## Acceptance Criteria
- All new APIs return deterministic ErrorEnvelope on errors.
- Time tracking operations are tenant-scoped and auditable.
- Only one running timer per user across a tenant.
- CSV exports are deterministic, bounded, and tenant-scoped.
- UI shows timer state, weekly totals, and approvals.
- CI green: ruff, black, pytest, smoke.

## Out of Scope
- Any external SaaS integrations or non-local persistence.
- Cross-tenant reporting or data aggregation.
- LLM usage without safe-mode gating.

## Risks & Mitigations
- **Race conditions for running timers** → unique index + transactional guard.
- **Tenant leakage** → all queries scoped by `tenant_id` and tested.
- **Approval misuse** → role-gated approvals + audit trail.
