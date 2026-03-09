# PR Quality Guard Report — 2026-03-05

## Ziel
Absicherung gegen zu kleine / nicht belegte PRs durch einen verbindlichen Guard in Dev-Workflow und CI.

## Eingeführte Gates
1. **MIN_SCOPE**: `>= 7` Dateien oder `>= 200` LOC.
2. **MIN_TESTS**: `>= 6` Test-Delta (Test-LOC).
3. **Evidence Required**: dieses Dokument muss in der PR vorhanden sein.
4. **Lane Overlap Check**: Fail bei Dateiüberlappung mit anderen lokalen `codex/*`-Branches.

## CI-Gate
- Command: `bash scripts/dev/pr_quality_guard.sh --ci`
- Workflow: `.github/workflows/ci.yml` (PR-Job `pr-quality-guard`)

## Simulationen
- Thin PR: **FAIL**
- Solid PR: **PASS**
- Overlap PR: **FAIL**

## 2026-03-08 Addendum
- Case: Layout-only hardening (`app/templates/layout.html`) to remove unused font preload warning.
- Initial result: **FAIL** (MIN_SCOPE, MIN_TESTS).
- Normalized result: **PASS target** after adding focused regression tests and evidence docs without widening runtime scope.

## 2026-03-09 Addendum
- Case: Session-tenant enforcement for generic Tool Actions API execution path.
- Security objective: block cross-tenant payload spoofing via `/api/<tool>/actions/<name>`.
- Evidence set:
  - Runtime enforcement in `app/modules/actions_api.py`
  - Integration regression in `tests/integration/test_emailpostfach_ai_actions.py`
  - Additional regression coverage in:
    - `tests/domain/aufgaben/test_actions_api.py`
    - `tests/domain/einstellungen/test_settings_actions_api.py`
  - Policy docs:
    - `docs/security/SESSION_TENANT_ENFORCEMENT_POLICY.md`
    - `docs/security/TOOL_ACTIONS_TENANT_BINDING_POLICY.md`
