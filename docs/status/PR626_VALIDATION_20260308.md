# PR 626 Validation Snapshot

## Objective
Enforce admin-only permission for settings mutation action.

## Validation Commands
- `python -m pytest -q tests/domain/aufgaben/test_actions_api.py`
- `python -m pytest -q tests/security/test_settings_action_admin_guard.py`
- `python -m pytest -q tests/integration/test_settings_action_update_contract.py`

## Assertions
- Operators cannot call `setting.update`.
- Admins can call `setting.update` without approval-token side path.
- Action catalog exposes canonical `admin` permission metadata.
