# Phase 1 Spec: Stability, Security, Chat Reliability (Tasks 1–30)

## Scope
Deliver the foundational stability and security requirements and fix chat reliability. This phase implements tasks 1–30 with a focus on:
- Spec/ADR coverage and constitution alignment.
- Error envelope standardization and request correlation.
- Deny‑by‑default policy enforcement and tests.
- Chat reliability (no redirect failures, retries, timeouts, and suggestions).

## Goals
- All API endpoints return a consistent `{ok:false, error:{code,message,details}}` envelope.
- Every request has a correlation ID in logs and responses.
- Public endpoints `/api/ping` and `/api/health` never redirect.
- Chat reliability: clear error states, retry/backoff, timeouts, and history persistence.
- Tenant isolation and unknown role denial are test‑verified.

## Non‑Goals
- Full connector implementations (handled in later phases).
- Vector search integration.

## Contracts
- Maintain `/contracts/openapi.yaml` + JSON schemas in `/contracts/schemas`.
- Define error envelope schema under `contracts/schemas/ErrorEnvelope.json`.

## Implementation Plan (Tasks 1–30)
1. Add `/docs/CONSTITUTION.md` and link from README.
2. Add ADR template and ensure ADRs for multi‑tenant model, policy gates, connector architecture.
3. Add ruff/black config + pre‑commit, wire into CI.
4. Standardize API error envelope across endpoints.
5. Add request‑id middleware + structured logging.
6. Ensure `/api/ping` and `/api/health` are public (no redirects).
7. Expand smoke test: login, chat POST, search, upload, health.
8. Add tenant scoping tests.
9. Add unknown role regression tests.
10. Add integration test harness with temp dirs + sqlite.
11. Add threat model doc.
12. Add provenance tagging for all text chunks (source + trust).
13. Enforce policy gate before tool actions (allowlist per role+intent).
14. Safe summarize mode for untrusted content.
15. Add prompt‑injection test corpus + automated tests.
16. Add output sanitization for UI rendering.
17. Ensure audit log table and usage is verified in tests.
18. Add rate limits + payload size limits.
19. Add CSRF/session hardening for web endpoints.
20. Add secrets handling doc + `.env.example`.
21. Reproduce chat not responding (document root cause).
22. Fix root cause (JS/API/redirect/timeout).
23. Add client‑side retry with backoff + visible error state.
24. Add server‑side timeout + graceful error response.
25. Add chat history persistence per tenant (sqlite).
26. Add suggestion chips + deterministic intent clarification flows.
27. Add DEV‑only explain‑why panel (intent, policy decision, chosen agent).
28. Add chat latency test (smoke).
29. Add “copy result” + “create task from chat” buttons.
30. Add “safe mode toggle” (LLM disabled, deterministic only).

## Acceptance Criteria
- `pytest -q` and `python -m app.smoke` pass.
- Chat endpoint always returns JSON (no redirects for API paths).
- Unknown roles are denied without 500s.
- Correlation IDs appear in logs and response headers.
