# Dev Quality Commands

- Dev fast path:
  - `python -m app.devtools.triage --fast --bench`
- CI/Release gate:
  - `python -m app.devtools.triage --ci`
- Write benchmark baseline:
  - `python -m app.devtools.triage --bench --write-baseline`

## Health checks

- Run health checks directly:
  - `python -m app.health --mode ci`
  - `python -m app.health --mode runtime`
- Include health in triage:
  - `python -m app.devtools.triage --health --health-mode ci`
- Write health JSON report:
  - `python -m app.devtools.triage --health --health-json reports/health.json`

## Warning gate

- Fail triage on warnings:
  - `python -m app.devtools.triage --ci --fail-on-warnings`
- Ignore known warning patterns:
  - `python -m app.devtools.triage --ci --ignore-warning-regex "swigvarlink"`
