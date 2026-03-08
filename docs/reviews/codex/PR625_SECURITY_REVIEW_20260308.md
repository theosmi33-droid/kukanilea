# PR 625 Security Review (Dev Backdoor Removal)

## Risk Addressed
- Hardcoded `dev/dev` credential shortcut in login path enabled unintended account access.

## Behavior After Fix
- Login only succeeds for persisted user records with matching password hash.
- No implicit auto-upsert for `dev` user during authentication.
- No auto-membership creation during authentication.

## Evidence
- `tests/test_login_security.py::test_dev_backdoor_credentials_are_rejected`
- `tests/security/test_login_dev_backdoor_block.py::test_dev_credentials_do_not_create_membership`
- `tests/integration/test_login_dev_user_requires_real_record.py::test_dev_user_requires_db_password_not_literal_dev`
