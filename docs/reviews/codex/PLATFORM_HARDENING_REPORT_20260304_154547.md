# PLATFORM HARDENING REPORT

## Scope
- Reproducible bootstrap script (`scripts/bootstrap.sh`)
- Environment doctor script (`scripts/doctor.sh`)
- Makefile developer targets
- CI corridor split (smoke vs full)
- Developer docs updates

## Implemented Changes
1. Added idempotent bootstrap flow with:
   - `.python-version` runtime guard
   - `.build_venv` creation/reuse
   - requirements + dev requirements installation
   - playwright install step (optional via `BOOTSTRAP_SKIP_PLAYWRIGHT=1`)
   - pre-commit hook installation
2. Added doctor diagnostics with PASS/FAIL for required system/runtime dependencies.
3. Added Make targets:
   - `make bootstrap`
   - `make doctor`
   - `make test-smoke`
4. Updated CI workflow to explicit corridor:
   - `smoke-corridor` (`lint + unit-smoke + healthcheck`)
   - `full-validation` as separate follow-up job
5. Updated README quickstart to one-command bootstrap and added `docs/dev/BOOTSTRAP_AND_DOCTOR.md`.

## Required Validation Runs
- `./scripts/bootstrap.sh` failed in this environment due blocked package index/proxy (403 while resolving setuptools/pip dependencies).
- `./scripts/doctor.sh` failed (missing `gh` and playwright runtime in current container).
- `pytest -q` failed during collection because bootstrap could not install Python dependencies (e.g., flask, pydantic, cryptography).
- `./scripts/ops/healthcheck.sh` failed because `.build_venv` lacks pytest (dependency install step failed).
- `./scripts/ops/launch_evidence_gate.sh --fast` failed without `REPO`; rerun with `REPO=owner/repo` still fails due missing/invalid git main reference in this environment.
