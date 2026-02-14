# CODEX-PROMPT — CI Hardening + Security Regression Suite v1

Repo: <REPO_ROOT>  
Base branch: main  
Branch: chore/ci-hardening-security-suite-v1

## ZIEL
1) GitHub Actions: `triage --ci` standardisieren (inkl. `ignore-warning-regex`, `fail-on-warnings`)  
2) Security Regression Tests:
- templates: forbid `|safe` in untrusted contexts
- imports: forbid `subprocess/os.system/eval/exec/requests/socket`
- eventlog: payload key allow/deny patterns (no email/phone/message/body/subject)

## HARTE REGELN
- Keine Produktivlogik ändern (nur CI + Tests).
- Kein Netzwerk in tests.

## ARBEITSPAKETE
### A) GH Actions anpassen
- Unify `triage` invocation.

### B) Add tests
- `tests/test_security_templates_no_safe.py`
- `tests/test_security_forbidden_imports.py`
- `tests/test_security_eventlog_payload_keys.py`

## QUALITY
- Alle bestehenden Gates bleiben grün.

```bash
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
