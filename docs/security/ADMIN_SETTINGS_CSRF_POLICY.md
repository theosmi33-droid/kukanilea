# Admin Settings CSRF Policy

Date: 2026-03-08
Scope: `/admin/settings/*` and `/admin/context/switch` write routes

## Policy
- All state-changing admin settings routes must use `@csrf_protected`.
- All HTML settings forms posting to admin settings routes must include
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- Missing or invalid CSRF token must fail closed with HTTP `403`.

## Regression Coverage
- `tests/security/test_admin_settings_csrf_enforcement.py`
- `tests/integration/test_admin_settings_form_csrf_contract.py`
- updated `tests/test_settings_governance.py` license upload flow for valid CSRF.

