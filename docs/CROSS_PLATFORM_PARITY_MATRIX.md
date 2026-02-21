# CROSS_PLATFORM_PARITY_MATRIX

Date: 2026-02-21

## Purpose
Track functional parity requirements between macOS and Windows for Beta/RC decisions.

## Core Flows

| Flow | macOS | Windows | Gate |
|---|---|---|---|
| Login + session lifecycle | PASS | BLOCKED | Must PASS on both for RC |
| CRM create/search/open | PASS | BLOCKED | Must PASS on both for RC |
| Tasks create/move/resolve | PASS | BLOCKED | Must PASS on both for RC |
| Docs upload/search/open | PASS | BLOCKED | Must PASS on both for RC |
| AI chat request + fallback UX | PASS | BLOCKED | Must PASS on both for RC |
| Error shell navigation (404/500) | PASS | BLOCKED | Must PASS on both for RC |
| Update check + rollback path | PASS | BLOCKED | Must PASS on both for RC |
| Installer launch and trust checks | BLOCKED | BLOCKED | Distribution evidence required |

## Status Rules

- Beta may ship with platform scope limitation if explicitly documented.
- RC requires parity for mandatory flows on all in-scope platforms.
- Any platform gap without explicit scope note must be treated as `FAIL`.

## Evidence

- E2E report links.
- Distribution verification reports.
- Platform-specific run outputs and issue references.
