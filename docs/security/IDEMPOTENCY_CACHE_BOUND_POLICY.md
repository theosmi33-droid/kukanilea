# Idempotency Cache Bound Policy

Date: 2026-03-08

- Idempotency cache must enforce a hard upper bound.
- Capacity pressure must evict oldest entries first.
- Guard against memory growth from unbounded key cardinality.

