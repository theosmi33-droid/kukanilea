# ADR-0008: DEV Import Pipeline for Intake Data

## Status
Accepted

## Context
We need a deterministic, audited way to ingest customer data from a local import directory without relying on external services. User tests show that indexing must be immediate, OCR must run on access, and tooling must remain deny-by-default.

## Decision
Introduce a DEV-only import pipeline endpoint (`/api/dev/import/run`) that scans `IMPORT_ROOT`, computes sha256, extracts text (with OCR), and upserts index records. The endpoint is allowlisted via `IMPORT_ROOT` and logs audit entries per imported file. Startup warms tenant indexes deterministically.

## Consequences
- Positive: deterministic local ingest, immediate index readiness, auditable imports.
- Negative: import runs are synchronous and may be slow on large directories.

## Alternatives Considered
- Automatic background watcher — rejected due to nondeterministic timing and additional complexity.
- Rely on manual uploads only — rejected because bulk intake workflows require automation.
