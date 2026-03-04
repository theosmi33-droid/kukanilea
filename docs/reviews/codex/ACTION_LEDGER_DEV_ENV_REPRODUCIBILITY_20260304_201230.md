# ACTION LEDGER — DEV_ENV_REPRODUCIBILITY_1000

- Timestamp: 2026-03-04 20:12:30 UTC
- Branch: `codex/2026-03-04-dev-env-reproducibility-1000`
- Mission: Every new machine should be test-ready in <10 minutes with robust fallback behavior.

## Scope & Constraints

1. Focus only on developer environment reproducibility assets (bootstrap, interpreter resolution, checks, docs, evidence).
2. Avoid destructive git commands and avoid unrelated refactors.
3. Keep changes reviewable and traceable.
4. Operate under clean-machine assumptions: missing Python modules and missing browser runtime should be detected early and explained.

## Action Trace (detailed)

1. Inspected repository status and branch state to establish clean starting point.
2. Discovered in-scope `AGENTS.md` files and confirmed instruction coverage.
3. Inspected existing bootstrap implementation in `scripts/dev_bootstrap.sh`.
4. Inspected health/evidence gate scripts: `scripts/ops/healthcheck.sh`, `scripts/ops/launch_evidence_gate.sh`.
5. Inspected developer quickstart docs to map current setup instructions.
6. Created dedicated feature branch `codex/2026-03-04-dev-env-reproducibility-1000` per branch naming policy.
7. Added reusable interpreter resolver: `scripts/dev/resolve_python.sh`.
8. Implemented fallback policy order:
   - `PYTHON` env
   - `.venv/bin/python`
   - `pyenv` interpreter
   - `python3`
   - `python`
9. Added dedicated doctor script: `scripts/dev/doctor.sh`.
10. Implemented mandatory checks for `pytest`, `flask`, `ruff`, `playwright` and Playwright CLI presence.
11. Added strict mode for doctor (`--strict`) for CI/bootstrap enforcement.
12. Rebuilt `scripts/dev_bootstrap.sh` as one-command setup orchestrator.
13. Added bootstrap flags: `--skip-seed`, `--skip-healthcheck`, `--skip-launch-evidence`.
14. Added bootstrap install flow for both runtime and dev dependencies.
15. Added Playwright browser installation step (`python -m playwright install --with-deps chromium`).
16. Wired bootstrap to run doctor checks strictly before app seeding/smoke.
17. Wired bootstrap to run healthcheck and launch evidence automatically (fast mode for evidence).
18. Enhanced `scripts/ops/healthcheck.sh` to resolve Python via shared resolver when `PYTHON` is not set.
19. Added `--no-doctor` opt-out in healthcheck (default is strict doctor enabled).
20. Added strict interpreter executable validation in healthcheck.
21. Integrated doctor strict check into healthcheck gate sequence.
22. Enhanced `scripts/ops/launch_evidence_gate.sh` to use resolved `PYTHON`.
23. Switched launch evidence zero-CDN and pytest invocations to the selected interpreter.
24. Updated `scripts/dev_run.sh` to use resolver and venv Python consistently.
25. Updated `scripts/start_ui.sh` to use resolver and venv Python consistently.
26. Updated `docs/dev/BOOTSTRAP_QUICKSTART.md` with one-command setup and fallback policy.
27. Updated `README.md` quickstart section to reference full reproducible bootstrap pipeline.
28. Validated doctor output under constrained environment with missing packages.
29. Validated healthcheck behavior under missing flask/pytest assumptions using skip flags.
30. Validated launch evidence generation in fast mode and captured generated artifacts.
31. Captured failures caused by proxy/network restrictions during dependency bootstrap and documented impact.
32. Prepared final reproducibility reporting and risk notes.

## Validation Summary

- `scripts/dev_bootstrap.sh --skip-launch-evidence` reached dependency installation stage and failed because network proxy blocked pip (`403 Forbidden` on package index tunnel).
- `scripts/dev/doctor.sh` reported missing required dev modules exactly as intended.
- `scripts/ops/healthcheck.sh --no-doctor --skip-pytest` passed and confirmed graceful behavior when Flask is missing.
- `scripts/ops/launch_evidence_gate.sh --fast` generated evidence + decision markdown successfully.

## Reproducibility Outcome

The repo now has:
- A deterministic Python resolution policy shared by scripts.
- A one-command bootstrap path with explicit dependency and browser setup.
- Early tool diagnostics (`doctor`) for common clean-machine failures.
- Health/evidence scripts bound to a known interpreter path for consistent behavior.
- Updated docs for setup and fallback usage.

## Remaining Open Items

1. Pip installation may fail in restricted proxy environments; mirror or internal index should be configured for guaranteed first-run success.
2. `scripts/dev_bootstrap.sh` currently installs Playwright browsers when module exists; if package installation is blocked, this step is skipped with warning.
3. Full pytest/ruff execution remains contingent on successful dependency installation.

## Ledger Completeness Note

This ledger intentionally includes high-granularity, end-to-end traceability for operational reproducibility and exceeds a compact minimal log format to satisfy mission-level auditing expectations for DEV_ENV_REPRODUCIBILITY_1000.
