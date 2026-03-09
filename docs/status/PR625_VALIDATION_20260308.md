# PR 625 Validation Snapshot

## Objective
Remove hardcoded dev-login bypass and preserve normal credential flow.

## Validation Commands
- `python -m pytest -q tests/test_login_security.py`
- `python -m pytest -q tests/security/test_login_dev_backdoor_block.py`
- `python -m pytest -q tests/integration/test_login_dev_user_requires_real_record.py`

## Expected Outcomes
- `dev/dev` fails when no matching stored hash exists.
- Login no longer creates implicit `dev` user/membership records.
- Valid stored dev credentials still authenticate successfully.
