# SEC + PERF Gate Report

## Scope
Enterprise hardening for CSP, security guardrails, and measurable performance gates.

## Changes

1. **CSP hardening (`app/security.py`)**
   - Added strict directives: `base-uri`, `object-src 'none'`, `form-action`, `frame-ancestors`, `connect-src`, `upgrade-insecure-requests`.
   - Kept `'unsafe-inline'` for style/script as temporary legacy compatibility path.
   - **Risk/Impact:**
     - Risk reduced for object injection, clickjacking, mixed-content and rogue form posting.
     - Residual risk remains from legacy inline JS/CSS until template refactor to nonce/hash path.

2. **Security gates added**
   - New mandatory zero-external-requests scanner (`scripts/ops/zero_external_requests_scan.py`).
   - Healthcheck now enforces zero external requests.
   - Launch evidence gate now includes zero external requests + performance budget checks.
   - Added confirm/injection security tests (`tests/security/test_confirm_and_injection_gates.py`).
   - **Risk/Impact:**
     - Prevents accidental CDN/external URL regressions.
     - Strengthens evidence that write operations keep explicit confirm behavior.
     - Adds explicit regression test against backup path injection payloads.

3. **Performance gates added**
   - New benchmark gate (`scripts/ops/performance_gate.py`) with objective budgets:
     - cold start budget (`COLD_START_BUDGET_MS`)
     - Playwright smoke render budget (`PAGE_BUDGET_MS`) for core pages
   - **Risk/Impact:**
     - Prevents silent startup/render regressions in release flow.
     - Fails fast on budget breach.

4. **KPI pipeline**
   - Added `scripts/ops/kpi_snapshot.sh`.
   - Produces `docs/status/KPI_SNAPSHOT_<timestamp>.md` including gate outputs + exit codes.
   - **Risk/Impact:**
     - Creates timestamped release evidence for auditability.

5. **CI integration**
   - Added `.github/workflows/security-performance-gates.yml` with mandatory security + perf gates and required test commands.
   - **Risk/Impact:**
     - PRs are blocked when security/performance gates fail.

## Mandatory commands executed in this environment
- `./scripts/ops/healthcheck.sh --ci` → failed due missing Python runtime dependencies in container.
- `REPO=gensuminguyen/kukanilea ./scripts/ops/launch_evidence_gate.sh --skip-healthcheck` → report generated, overall gate failed in current environment.
- `PYENV_VERSION=3.12.12 python -m pytest -q tests/security tests/e2e` → failed due missing Flask/Playwright deps.
- `npm run test:e2e` → failed due missing Playwright browser binary + no local server.

## Release decision
**NO-GO in this container environment** due dependency/tooling limitations and missing Playwright browser runtime.
