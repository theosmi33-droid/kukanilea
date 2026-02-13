# Dev Quality Commands

- Dev fast path:
  - `python -m app.devtools.triage --fast --bench`
- CI/Release gate:
  - `python -m app.devtools.triage --ci`
- Write benchmark baseline:
  - `python -m app.devtools.triage --bench --write-baseline`

## Health checks

- Run health checks directly:
  - `python -m app.health --mode ci --json out.json`
  - `python -m app.health --mode runtime --json out.json`

- Include health in triage:
  - `python -m app.devtools.triage --health --health-mode ci`
  - `python -m app.devtools.triage --health --health-mode runtime`

Runtime semantics:
- Runtime mode is read-only. It must not create directories/files or write to configured production DBs.
- CI mode may use temporary/in-memory artifacts only.

## Warning gate

- Fail triage on warnings:
  - `python -m app.devtools.triage --ci --fail-on-warnings`
- Ignore known warnings via regex:
  - `python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "swigvarlink"`
