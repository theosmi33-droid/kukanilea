# Launch Evidence Gate Automation Report

- Timestamp: 2026-03-07T04:55:14+01:00
- Decision: **FAIL**
- Exit-Code: 3
- Repo: theosmi33-droid/kukanilea

## Gate Matrix

| Gate | Status | Note |
|---|---|---|
| Repo/CI | PASS | git HEAD resolvable |
| MIN_SCOPE | PASS | files=17 loc=878 |
| Health | PASS | healthcheck passed |
| Zero-CDN | PASS | guardrails passed |
| White-mode | PASS | no dark mode signatures |
| License | FAIL | status=LOCK:MISSING |
| Backup | PASS | backup/restore evidence + verification hooks verified |
| AI | PASS | AI operating contract present |
| MIN_TESTS | PASS | tests/ops test-count=53 |
| CI_GATE | PASS | pytest tests/ops passed |
| MIA_GATE7_SMOKE | PASS | gate7 smoke evidence generated in /Users/gensuminguyen/Kukanilea/evidence/operations/gate7_latest |
| MIA_GATE7_ARTIFACTS | PASS | gate7 artifacts contain required evidence matrix |
| MIA_UNCONTROLLED_WRITES | PASS | writes limited to controlled code/test/evidence paths |
| Evidence | PASS | evidence path matches required target |

## Totals

- PASS: 13
- WARN: 0
- FAIL: 1
