# REPORT_SECURITY_CHECKS

Date: 2026-02-21
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`

## Scope
- Tenant/RBAC/CSP/session regression checks
- Security scanner findings
- Pass/Fail against Security gate

## Pre-risk git status evidence
Command:
```bash
git status --porcelain=v1
```
Output:
```text
<clean>
```

## Evidence
### Security-focused pytest subset
Command:
```bash
pytest -q tests/test_tenant_isolation.py tests/test_rbac_permissions.py tests/test_security_templates_no_safe.py tests/test_security_forbidden_imports.py tests/test_security_eventlog_payload_keys.py tests/test_idle_timeout.py tests/test_csp_headers.py tests/test_no_external_fonts.py
```
Result:
- `19 passed in 2.41s`
- Evidence: `/tmp/kuka_pytest_security_subset.log`

### Security scan
Command:
```bash
python -m app.devtools.security_scan
```
Result:
- FAIL: 4 findings in `app/ollama_runtime.py`
- Evidence: `/tmp/kuka_security_scan_bench.log`

Findings:
1. `subprocess_shell` at line 56 (`subprocess.run` missing explicit `shell=False`)
2. `subprocess_timeout` at line 56 (missing explicit timeout)
3. `subprocess_shell` at line 72 (`subprocess.Popen` missing explicit `shell=False`)
4. `subprocess_timeout` at line 72 (missing explicit timeout)

### Triage
Command:
```bash
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```
Result:
- FAIL (`smoke`: chat latency too high)
- Evidence: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/triage_report.json`, `/tmp/kuka_triage_bench.log`

## Pass/Fail vs Release Gates (Security)
| Gate target | Status | Reason | Evidence |
|---|---|---|---|
| Beta: no known P0 leaks | PASS | tenant/rbac/csp/session regressions pass; no P0 leak found in this run | security pytest subset |
| RC: 0 open P0, 0 open High | FAIL | security_scan has open findings; severity needs closure before RC acceptance | `/tmp/kuka_security_scan_bench.log` |
| Prod: external security check + 0 High | FAIL | no external security assessment evidence in this run | n/a |

## How to verify
1. Fix `app/ollama_runtime.py` scanner findings.
2. Re-run `security_scan`, `triage`, and security subset tests.
3. Execute explicit authz negative tests (role escalation, unauthorized route access).
4. Attach logs with request IDs and CI links for release decision.

## Findings table
| Finding | Severity | Evidence | Repro | Suggested fix |
|---|---|---|---|---|
| subprocess policies incomplete in Ollama runtime | High (policy) | `/tmp/kuka_security_scan_bench.log` | Run `python -m app.devtools.security_scan` | set `shell=False` explicitly, add explicit timeout, document rationale |
| Chat smoke latency too high | Medium | `triage_report.json` | Run triage command | profile chat path, optimize provider routing and warmup, tune timeouts |
