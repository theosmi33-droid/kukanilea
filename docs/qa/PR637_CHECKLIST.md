# PR637 QA Checklist

- [ ] Repeated request with same idempotency key still returns deduplicated response.
- [ ] High-cardinality key stream does not grow cache without bound.
- [ ] Eviction keeps service responsive and deterministic.

