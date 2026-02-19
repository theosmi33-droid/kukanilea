# Beta Hotfix Policy

## When to patch
- `sev1`: patch immediately.
- `sev2`: patch when widespread or onboarding-blocking; otherwise batch.
- `sev3`: batch weekly or defer.

## Process
1. Create focused fix branch from `main`.
2. Land fix via PR to `main` (small diff, regression test included).
3. Run required gates:
   - `compileall`, `ruff`, `pytest`, `security_scan`, `triage`, `schema_audit`, `e2e` (where available).
4. Create release PR for next beta patch version (for example `1.0.0-beta.2`) with updated notes/changelog.
5. Tag and publish GitHub prerelease.

## Constraints
- No new runtime dependencies during beta unless explicitly approved.
- Keep fixes reversible.
- Avoid mixing unrelated refactors with hotfixes.
