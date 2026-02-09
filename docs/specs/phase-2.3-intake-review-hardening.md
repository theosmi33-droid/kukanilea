# Phase 2.3 — Intake→Review→Archive Hardening

## Context
User tests identified gaps in Re-Extract path resolution, open-token UX, DEV-only Settings visibility, and import automation for customer data.

## Goals
- Fix Re-Extract to use DB-backed paths and deterministic fallbacks.
- Ensure search results expose tokens and UI can open/copy them reliably.
- Restrict Settings UI/routes/APIs to DEV/ADMIN.
- Add DEV-only import pipeline endpoint tied to IMPORT_ROOT with auditing.
- Warm up tenant indexes on startup deterministically.

## Acceptance Criteria
1. Re-Extract uses the DB file path when the Eingang path is missing; failures return an ErrorEnvelope `FILE_NOT_FOUND` via API helpers.
2. Search results include `token`, UI open buttons call `openToken(token)`, and tokens are copyable.
3. Non-DEV/ADMIN users receive 403 ErrorEnvelope responses for settings access.
4. `/api/dev/import/run` scans `IMPORT_ROOT`, performs sha256 + upsert + index + audit, and is DEV-only.
5. Startup initializes schema, ensures FTS availability, and warms tenant indexes deterministically.
6. OpenAPI + schemas are updated for new/changed endpoints/fields.
7. Tests cover: search results include `token`, open by token, and settings access restrictions.

## Out of Scope
- Full Phase 2.2 Jobs/Tasks Core.
- UI redesign or new workflows beyond the open/copy token UX.
- LLM provider changes or cloud integrations.
