## Title
feat(automation): Phase 3.4 – Cron + email_draft hardening

## Why
Phase 3.3 introduced cron triggers and `email_draft`. This follow-up hardens semantics and safety:
- strict cron parsing rules (single supported format, explicit rejection of unsupported syntax)
- deterministic cron behavior tests (UTC normalization + per-minute idempotency coverage)
- stricter `email_draft` validation (template allowlist + payload limits)
- safer UI/import validation so invalid rules are blocked before execution

## Scope
- `app/automation/cron.py`
  - add strict cron guardrails: max length, char allowlist, explicit error reasons
- `app/automation/actions.py`
  - enforce `email_draft` subject/body limits
  - reject unknown placeholders
  - validate optional attachment IDs for tenant
  - run draft safety check and return warning metadata
- `app/web.py`
  - enforce same email-template guardrails in builder UI/import paths (`email_draft` + `email_send`)
- tests:
  - cron invalid syntax and length limits
  - UTC normalization behavior
  - `email_draft` template allowlist and length-limit failures
  - import/UI validation rejections for unsafe payloads
- docs:
  - update `/docs/AUTOMATION_BUILDER.md` with exact cron format constraints and draft safety limits

## Security Invariants
- no automatic send added
- no new dependencies
- fail-closed validation for cron/email template config
- tenant isolation unchanged
- logs remain redacted/metadata-only

## How To Verify
```bash
cd /Users/gensuminguyen/Tophandwerk/kukanilea-git
python -m compileall -q .
ruff check .
ruff format . --check
pytest -q
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
python -m app.devtools.schema_audit --json > /dev/null
```

## Rollback
- Revert this PR.
- Changes are additive validation/hardening and test/doc updates; no destructive migration path.
