# CODEX PROMPT - Competitive Learnings -> Product Execution (KUKANILEA)

Repo: `/Users/gensuminguyen/Tophandwerk/kukanilea-git`
Base: `main`
Target branch: `codex/feat/ops-intake-and-evidence-pack`

## Goal
Convert validated competitor learnings into 4 shippable capabilities without adding runtime dependencies:
1. Inbox Triage v1 (classify/summarize/route)
2. Evidence Pack export (timeline + attachments + request IDs)
3. Time-to-first-workflow setup metric
4. AI transparency + compliance surface hardening

## Guardrails
- No client-trusted authorization decisions.
- Tenant/RBAC rules remain server-side enforced.
- No regressions on CSP/offline/local-first defaults.
- External claims are benchmarks, not product facts.

## Phase 0 - Preflight
```bash
cd /Users/gensuminguyen/Tophandwerk/kukanilea-git
git status --short
git checkout main
git pull origin main
git checkout -b codex/feat/ops-intake-and-evidence-pack
```

## Phase 1 - Inbox Triage v1
### Deliverables
- Intake classifier labels: `lead`, `support`, `invoice`, `appointment`, `unknown`
- Deterministic fallback queue when confidence below threshold
- Summary generation (short factual summary)
- Route recommendation (`owner_role`, `queue`, `priority`)

### Implementation sketch
- Add `app/intake/triage.py`:
  - `triage_message(text, metadata) -> {label, confidence, summary, route}`
- Add endpoint `POST /api/intake/triage` (auth required)
- Persist events with request ID and tenant scope
- Add tests:
  - `tests/test_intake_triage.py`

## Phase 2 - Evidence Pack export
### Deliverables
- one-click export for job/task/case containing:
  - timeline events (timestamp, actor, status)
  - attachments list
  - request IDs and references
- output format: JSON + optional PDF wrapper if existing stack supports it

### Implementation sketch
- Add `app/reports/evidence_pack.py`
- Endpoint `GET /api/reports/evidence-pack/<entity_id>`
- enforce composite lookup `(tenant_id, entity_id)`
- tests: `tests/test_evidence_pack.py`

## Phase 3 - Time-to-first-workflow KPI
### Deliverables
- setup funnel instrumentation for first-run workflow milestones:
  - first_login
  - first_customer
  - first_document
  - first_task
  - first_ai_summary
- report endpoint for aggregate time-to-first-workflow

### Implementation sketch
- Add milestone events to existing eventlog system
- Add simple report query in `app/insights/activation.py`
- tests: `tests/test_activation_kpi.py`

## Phase 4 - Compliance surface
### Deliverables
- AI disclosure banner/message in assistant UI and API payload metadata
- signature classification text in report/approval UI (no overclaim vs QES)
- retention config docs for location/time activity data

### Implementation sketch
- UI: add assistant disclosure in `templates/*assistant*`
- API: include `ai_disclosure=true` metadata where applicable
- Docs updates:
  - `docs/SECURITY.md`
  - `docs/CONFIGURATION.md`
  - `docs/RELEASE_GATES.md`

## Validation gates
```bash
python -m compileall -q .
ruff check .
ruff format . --check
pytest -q
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
python -m app.devtools.schema_audit --json > /dev/null
```

## Commit plan
1. `feat(intake): add deterministic inbox triage v1`
2. `feat(reports): add tenant-scoped evidence pack export`
3. `feat(metrics): add time-to-first-workflow activation milestones`
4. `feat(compliance): add ai transparency and signature-level clarifications`

## PR title
`feat(ops): inbox triage + evidence pack + activation KPI + compliance UX`

## PR body (short)
- Why: convert market-proven ops patterns into measurable local-first workflows
- What: triage, evidence export, activation KPI, compliance UX
- Security: tenant/RBAC enforced; no client-trusted decisions
- How to test: full gate command list above
