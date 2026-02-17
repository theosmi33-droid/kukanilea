# ADR-0010: TEXT-ID Migration Strategy (No Main Rewrite)

Status: accepted
Date: 2026-02-17

## Context
The codebase contains legacy tables with `INTEGER PRIMARY KEY AUTOINCREMENT` and mixed tenant coverage.
A direct global rewrite is high risk and not acceptable for active branches.

## Decision
We adopt a phased migration strategy with strict backward compatibility:

1. Inventory and classify
- Run schema audit on core/auth DBs.
- Classify tables by risk and coupling.

2. Compatibility phase
- Keep existing integer PKs during transition.
- Introduce TEXT IDs for new tables immediately.
- For migrated legacy tables, add parallel TEXT ID columns, backfill, and dual-read/dual-write.

3. Cutover phase
- Switch references and APIs to TEXT IDs.
- Keep compatibility views/adapters until verification completes.

4. Cleanup phase
- Remove integer-ID compatibility paths only after two green release cycles.

## Guardrails
- No destructive in-place table rewrite on `main`.
- Additive and idempotent migrations only.
- Tenant isolation must be preserved in every migration step.
- CI must include schema audit evidence.

## Consequences
- Migration takes multiple PRs but remains reviewable and low risk.
- Temporary dual-ID code paths increase complexity short-term.
- Reduced outage/regression risk compared to one-shot migration.
