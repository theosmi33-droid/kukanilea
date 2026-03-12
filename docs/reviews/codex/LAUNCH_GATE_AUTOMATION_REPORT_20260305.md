# Launch Evidence Gate Automation Report

- Timestamp: 2026-03-12T12:38:55+00:00
- Decision: **FAIL**
- Exit-Code: 3
- Repo: unknown

## Gate Matrix

| Gate | Status | Note |
|---|---|---|
| Repo/CI | PASS | git HEAD resolvable |
| MIN_SCOPE | FAIL | files=7 loc=140 (need files>=8 or loc>=230; origin/main unavailable in local clone possible) |
| Health | WARN | skipped by flag |
| E2E_Runtime | WARN | playwright.sync_api unavailable (python e2e skipped by contract) |
| Zero-CDN | PASS | guardrails passed |
| White-mode | PASS | no dark mode signatures |
| License | FAIL | status=LOCK:MISSING |
| Backup | PASS | backup/restore evidence + verification hooks verified |
| AI | PASS | AI operating contract present |
| MIN_TESTS | PASS | tests/ops test-count=71 |
| CI_GATE | PASS | pytest tests/ops passed |
| MIA_GATE7_SMOKE | PASS | gate7 smoke evidence generated in /workspace/kukanilea/evidence/operations/gate7_latest |
| MIA_GATE7_ARTIFACTS | PASS | gate7 artifacts contain required evidence matrix |
| MIA_UNCONTROLLED_WRITES | FAIL | uncontrolled writes detected outside controlled paths |
| Evidence | PASS | evidence path matches required target |

## Totals

- PASS: 10
- WARN: 2
- FAIL: 3
