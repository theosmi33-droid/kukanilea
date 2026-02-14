# ADR 0016: Knowledge ICS Source v0

## Status
Accepted

## Context
Knowledge Base v1 already supports tenant-safe chunks and policy-gated sources. Calendar data is a high-value source, but parser and privacy risks are non-trivial.

## Decision
Implement a minimal upload-only ICS source (`.ics`) with strict parser and storage limits:
- No network/IMAP/OAuth integration.
- Default deny (`allow_calendar=0`).
- Ingest only VEVENT metadata (`DTSTART`, `DTEND`, `SUMMARY`, `LOCATION`).
- Ignore risky/high-noise fields (`ATTACH`, `RRULE`, attendee/contact-like fields).
- Store only redacted chunk snapshots (no raw ICS persistence).

## Security rationale
- Line unfolding is applied before parsing to avoid malformed-field ambiguities.
- Hard size/line/event/chunk limits reduce DoS risk.
- Eventlog payloads remain PII-free and metadata-only.

## Consequences
- v0 provides safe searchable calendar context with low operational risk.
- Recurrence expansion and rich calendar semantics are intentionally out of scope for v0.
- Future versions can extend parsing in bounded, test-first increments.
