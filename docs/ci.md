# CI Notes

## Why warning ignore regex exists
The CI triage step runs with `--fail-on-warnings`. Some third-party bindings emit non-actionable warnings (for example SWIG-related deprecations) that are not regressions in this repository.

To keep CI strict but stable, we use:

```bash
python -m app.devtools.triage --ci --fail-on-warnings \
  --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```

## Review rule
Do not broaden the ignore regex without a concrete reason. New warning classes should be fixed at source when possible.

## Security regression subset
CI runs a focused security subset after the full test suite:

- `tests/test_security_templates_no_safe.py`
- `tests/test_security_forbidden_imports.py`
- `tests/test_security_eventlog_payload_keys.py`

These tests protect against template XSS bypasses, dangerous execution/network imports in sensitive modules, and accidental PII leakage in eventlog payloads.
