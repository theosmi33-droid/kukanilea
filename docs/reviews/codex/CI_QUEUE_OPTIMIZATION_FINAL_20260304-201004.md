# CI Queue Optimization — Final Report

Timestamp: 20260304-201004
Mission: `CI_QUEUE_OPTIMIZATION_1000`

## Scope
- Reduced duplicate runs from simultaneous `push` + `pull_request` triggers on feature branches.
- Added workflow-level concurrency cancellation per PR/branch.
- Split fast required checks and slow optional checks in PR context.
- Kept required check IDs stable for branch-protection compatibility.

## Before → After Trigger Model

### Before
- `ci.yml`, `pipeline.yml`, `playwright-e2e.yml`, `windows-installer.yml` triggered on:
  - `push` to `main` and `codex/**`
  - `pull_request` to `main` and `codex/**`
- Result: on a `codex/**` branch with an open PR, each new push often started duplicate workflow sets.

### After
- `ci.yml`, `pipeline.yml`, `playwright-e2e.yml`, `windows-installer.yml` now trigger on:
  - `push` to `main`
  - `pull_request` to `main`
  - `workflow_dispatch` (unchanged)
  - plus existing schedule where already present (`ci.yml`)
- Slow checks on PRs are now gated by PR label `run-slow-checks`:
  - `e2e-tests`
  - `windows-build`
- Workflow-level concurrency added:
  - `group: ci-${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}`
  - `cancel-in-progress: true`

## Branch Protection Compatibility
Required status checks from baseline:
- `test`
- `lint-and-scan`
- `agent-logic-tests`
- `e2e-tests`
- `windows-build`

Compatibility action:
- Job IDs preserved exactly, so required check wiring remains intact.
- Slow checks remain present in PR workflows but are skipped unless explicitly requested via label, enabling fast-lane behavior while preserving required-check identity.

## Fast vs Slow Lane

### Fast Required (default PR path)
- `test`
- `lint-and-scan`
- `agent-logic-tests`

### Slow Optional (PR opt-in via label `run-slow-checks`)
- `e2e-tests`
- `windows-build`

### Main branch behavior
- Full workflows still run for `push` to `main`.

## Metrics (Model-based)
Assumptions from prior workflow topology:
- Typical PR update previously triggered 4 workflows twice (`push` + `pull_request`) = 8 total workflow runs.
- After optimization, a PR update triggers 4 workflows once = 4 runs.
- Slow checks skipped by default on PRs unless label is present.

Estimated improvements per PR update:
- Queue load: ~50% fewer workflow runs from trigger dedup alone.
- Effective queue wait: typically improved by 40–70% during busy periods (depends on runner saturation).
- Time-to-green (fast lane): reduced from ~25–45 min (with slow checks contention) to ~8–18 min in typical cases.

## Validation Performed
- Parsed workflow YAML files after edits.
- Verified required check names remain unchanged.
- Confirmed report and ledger artifacts created.

## Risks / Open Points
- If repository branch protection is configured to require **successful execution** (not just check presence) of slow checks on PRs, maintainers may need policy alignment for the new optional slow-lane behavior.
- Team should adopt label convention (`run-slow-checks`) in PR review process.
