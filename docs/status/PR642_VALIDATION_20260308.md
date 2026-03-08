# PR642 Validation (CSRF hardening for admin settings)

## Changed
- Enforced CSRF decorator coverage on admin settings write handlers.
- Added hidden CSRF form fields to admin settings templates.
- Updated governance regression for license upload to include valid CSRF.
- Added dedicated security/integration regression tests for CSRF enforcement.

## Local Validation
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/test_settings_governance.py`
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/security/test_admin_settings_csrf_enforcement.py`
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/integration/test_admin_settings_form_csrf_contract.py`

## Expected Risk Reduction
- Blocks cross-site POSTs against admin settings endpoints without valid session CSRF token.
- Aligns template-posted forms with route-level CSRF enforcement to avoid accidental 403 regressions.

