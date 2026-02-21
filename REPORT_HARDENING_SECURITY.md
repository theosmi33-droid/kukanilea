# REPORT_HARDENING_SECURITY

Date: 2026-02-21
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`
Branch: `codex/bench-and-stability`

## Scope
- Deny-by-default regression (unauthenticated + low role)
- Cross-tenant no-leak behavior
- Logout session invalidation
- CSP and Request-ID headers on representative responses

## Pre-run git status
Command:
```bash
git status --porcelain=v1
```
Output:
```text
?? REPORT_HARDENING_SECURITY.md
?? tests/test_hardening_security.py
```

## Commands
```bash
pytest -q tests/test_hardening_security.py
```

## Results
| Test case | Expected | Actual | Status |
|---|---|---|---|
| Unauthenticated protected API access (`/api/tasks`, `/api/customers`, `/api/audit`) | 401 + no sensitive fields + request-id header | 401 responses with sanitized payload shape; `X-Request-Id` present | PASS |
| Low-role to admin endpoint (`/api/audit`) | 403 | 403 response for `OPERATOR`; request-id header present | PASS |
| Cross-tenant access attempt (`/api/tasks/<id>/move`) | 403/404 and no tenant-A content leak | 404 for tenant mismatch; response body excludes source task title/details | PASS |
| Logout invalidates session | pre-logout allowed; post-logout denied | `GET /api/tasks` 200 before logout, then 401 after logout | PASS |
| CSP + Request-ID on HTML response (`/login`) | CSP header present + request-id header present | `default-src 'self'` and `font-src 'self'` present; `X-Request-Id` present | PASS |

## Raw output
```text
.....                                                                    [100%]
5 passed in 0.85s
```
