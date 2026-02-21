## Title
feat(metrics): add activation milestones and time-to-first-workflow KPI

## Why
Phase 3 adds measurable onboarding funnel telemetry so we can validate the competitive benchmark for fast first-value workflows.

## Scope
- Added activation milestone tracker (`first_login`, `first_customer`, `first_document`, `first_task`, `first_ai_summary`).
- Added activation report aggregation with tenant scoping and percentile metrics.
- Added API endpoint `GET /api/insights/activation`.
- Wired milestone recording into existing server-side flows (login, customer create, task create, knowledge note create, chat).
- Added regression tests for idempotent milestone writes, KPI aggregation, endpoint tenant isolation, and task-flow instrumentation.

## Security notes
- Milestone data remains tenant-scoped.
- Writes are idempotent per tenant+user+milestone to prevent noisy duplicates.
- No prompt/message bodies are persisted in milestone payloads.

## How to verify
```bash
pytest -q tests/test_activation_kpi.py tests/test_intake_triage.py tests/test_evidence_pack.py
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
