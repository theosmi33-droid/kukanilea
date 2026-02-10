# ADR-0009: Local-first SQLite as Source of Truth

- **Status:** Accepted
- **Date:** 2026-02-09
- **Decision owners:** KUKANILEA maintainers

## Context

KUKANILEA targets Handwerk workflows where:
- Connectivity is unreliable (on-site work, basements, mobile hotspots).
- Customer documents and audit trails are sensitive (GDPR/DSGVO).
- Determinism and reproducibility matter more than horizontal scaling.

The system also relies on a “DB truth + filesystem reality” model:
- Files live on disk (reality).
- Metadata, meaning, access control, and auditing live in the DB (truth).

## Decision

Use **SQLite (local file DB)** as the primary source of truth for:
- Tenant-scoped entities (users, memberships, customers, docs, tasks, time tracking).
- Indexing tables (FTS/metadata).
- Audit log.

The filesystem remains the storage for document bytes, while the DB controls structure, permissions, and provenance.

## Options considered

1. **SQLite (chosen)**
   - ✅ Zero external services
   - ✅ Easy backup/restore (single file + predictable folder tree)
   - ✅ Deterministic, fast for local workloads
   - ✅ Great fit for single-machine / small team per tenant

2. **PostgreSQL (rejected for now)**
   - ✅ Strong concurrency, RLS, scale
   - ❌ Adds operational burden (server, migrations, monitoring)
   - ❌ Harder to keep “offline-first” as default
   - ❌ Increases attack surface and deployment complexity

3. **Cloud DB (rejected)**
   - ❌ Violates local-first default and creates unavoidable data egress risk

## Consequences

### Positive
- Installation becomes “clone + run” (or packaged installer later).
- Offline operation is the default.
- Security posture improves (data stays on device by default).

### Negative / Mitigations
- SQLite write contention with multiple concurrent writers.
  - Mitigation: use WAL mode, short transactions, careful indexing.
- Multi-user concurrency needs discipline.
  - Mitigation: server-side locks/constraints (e.g., “one running timer per user”), plus tests.

## Guardrails

- Every table includes `tenant_id`.
- Every query must constrain by `tenant_id`.
- Deny-by-default policy before any meaningful action.
- All errors returned as ErrorEnvelope for API determinism.
