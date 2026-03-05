# Launch Evidence Gate Automation Report

- Timestamp: 2026-03-05T18:14:38+00:00
- Decision: **NO-GO**
- Exit-Code: 3
- Repo: unknown

## Gate Matrix

| Gate | Status | Note |
|---|---|---|
| Repo/CI | PASS | git HEAD resolvable |
| MIN_SCOPE | FAIL | files=5 loc=202 (need files>=8 or loc>=230; origin/main unavailable in local clone possible) |
| Health | FAIL | healthcheck failed |
| Zero-CDN | PASS | guardrails passed |
| White-mode | PASS | no dark mode signatures |
| License | FAIL | status=LOCKED:MISSING |
| Backup | PASS | backup/restore evidence verified |
| AI | PASS | AI operating contract present |
| MIN_TESTS | PASS | tests/ops test-count=33 |
| CI_GATE | PASS | pytest tests/ops passed |
| Evidence | PASS | evidence path matches required target |

## Totals

- PASS: 8
- WARN: 0
- FAIL: 3
