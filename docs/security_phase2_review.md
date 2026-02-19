# Phase 2 Security Review

## Automated checks
Run:

```bash
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings
python -m app.devtools.schema_audit --json > /dev/null
python scripts/security_phase2_check.py
```

## Manual checks
- Verify fail-closed behavior when `EMAIL_ENCRYPTION_KEY` is missing.
- Verify read-only blocks all mutating routes (`POST/PUT/PATCH/DELETE`).
- Confirm no tenant data leaks across list/search routes.
- Confirm AI and workflow events do not log message bodies in event payloads.

## Exit criteria
- No new critical or high security findings.
- All known findings have owner, severity, and mitigation timeline.

## Current note
- `pip-audit` may report vulnerabilities in the local `pip` installer package
  itself. Track this at environment level (upgrade build/runtime pip), it is not
  an application dependency shipped by KUKANILEA.
