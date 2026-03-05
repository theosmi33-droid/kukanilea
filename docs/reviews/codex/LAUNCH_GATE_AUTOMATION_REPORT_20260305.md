# Launch Evidence Gate Automation Report

- Timestamp: 2026-03-05T09:15:04+00:00
- Decision: **NO-GO**
- Exit-Code: 3
- Repo: unknown

## Gate Matrix

| Gate | Status | Note |
|---|---|---|
| Repo/CI | PASS | git HEAD resolvable |
| MIN_SCOPE | PASS | files=8 loc=140 |
| Health | FAIL | healthcheck failed |
| Zero-CDN | PASS | guardrails passed |
| White-mode | PASS | no dark mode signatures |
| License | FAIL | license file missing |
| Backup | PASS | backup tests passed |
| AI | PASS | AI operating contract present |
| MIN_TESTS | PASS | tests/ops test-count=17 |
| CI_GATE | PASS | pytest tests/ops passed |
| Evidence | PASS | evidence path matches required target |

## Totals

- PASS: 9
- WARN: 0
- FAIL: 2
