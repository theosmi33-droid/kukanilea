# STATUS 2026-03-08 - Layout Preload Hardening

## Change
- Removed direct font preload for `/static/fonts/inter/InterVariable.woff2` from `app/templates/layout.html`.
- Kept local font delivery via `/static/css/fonts.css`.

## Reason
- Browser stress navigation showed repeated preload warnings for a font resource reported as not used in time.
- Goal was to reduce console noise while preserving Zero-CDN and local-first guarantees.

## Evidence
- Guardrails: `PYENV_VERSION=3.12.0 python scripts/ops/verify_guardrails.py`
- Targeted tests:
  - `tests/security/test_layout_shell_hardening.py`
  - `tests/security/test_verify_guardrails.py`
  - `tests/test_tasks_performance_contract.py`
  - `tests/integration/test_navigation_smoke.py`
- Full suite baseline previously verified locally: `970 passed`.

## Notes
- Existing local user edits in `app/templates/kanban.html`, `app/templates/projekte/index.html`, and `app/templates/tasks.html` were intentionally not modified by this hardening change.
