# PR 626 Security Review (Settings Update Permission)

## Risk Addressed
- Privileged settings mutation was exposed to non-admin roles through `write` permission.

## Fix Summary
- `setting.update` action now requires `admin` permission.
- API permission-denied path returns the correct structured JSON + status.
- Regression tests assert operator denial and admin success.

## Evidence
- `tests/domain/aufgaben/test_actions_api.py::test_settings_setting_update_requires_admin_role`
- `tests/domain/aufgaben/test_actions_api.py::test_settings_setting_update_admin_can_persist`
- `tests/security/test_settings_action_admin_guard.py::test_settings_update_rejects_operator_even_with_approval_token`
- `tests/integration/test_settings_action_update_contract.py::test_settings_action_catalog_reports_admin_permission`
