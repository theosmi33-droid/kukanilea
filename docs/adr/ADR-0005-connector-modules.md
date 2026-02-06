# ADR-0005: Connector architecture as optional modules

## Status
Accepted

## Context
Mail/calendar/chat connectors should be extensible without breaking local-first core.

## Decision
- Define connector interfaces as optional modules (mail, calendar, messaging).
- Core remains functional with no external connectors.
- Connectors are feature-flagged and scoped by tenant + policy.

## Consequences
- Implementation can be staged without destabilizing core.
- Security boundaries remain intact.

## Alternatives Considered
- Integrate SaaS APIs directly in core (rejected: violates local-first and increases risk).
