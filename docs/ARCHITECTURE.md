# KUKANILEA Architecture (Local-first)

Last updated: 2026-02-17

## Runtime Stack
- Backend: Python + Flask
- Data: SQLite (tenant-isolated)
- Frontend: Jinja templates + HTMX + Tailwind CSS
- OCR: Tesseract (optional, probed and allowlisted)
- CI/Quality: ruff + pytest + triage gate

No React, Vue or Alpine.js runtime is part of the supported stack.

## Core Principles
- DB is source of truth.
- Tenant isolation is mandatory.
- Default-deny policy and explicit allowlists.
- Offline-first execution.
- Deterministic diagnostics and stable error contracts.

## Security Boundaries
- READ_ONLY blocks all mutations.
- Eventlog payloads store IDs/metrics only (no PII payload keys).
- OCR and mail content must be redacted before persistence.
- Tesseract execution uses list argv + `shell=False`.

## Extension Policy
- Any dependency or stack change requires ADR.
- New features must include tests for tenant isolation and security-sensitive behavior.
