## Summary
- 

## Why
- 

## Scope
- 

## Verification
- [ ] python -m compileall -q .
- [ ] ruff check . --fix
- [ ] ruff format .
- [ ] pytest -q
- [ ] python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"

## Security / Compliance
- [ ] No PII in eventlog payloads
- [ ] `secrets.compare_digest()` used for token/code/hash comparisons
- [ ] `subprocess` uses `shell=False` + timeout
- [ ] READ_ONLY guard enforced for mutating routes

## Review Checklist
- [ ] I completed `docs/PR_REVIEW_CHECKLIST.md`

## Rollout / Rollback
- Rollout:
- Rollback:
