# Login Backdoor Removal Policy

## Rules
- Authentication must never rely on hardcoded credentials.
- Authentication must not auto-create users or memberships during login.
- Dev users are treated like any other account and must exist in the auth store.

## Enforcement
- Login path checks only persisted `user.password_hash`.
- Membership presence is mandatory for successful session bootstrap.
- Regression tests block reintroduction of `dev/dev` bypass logic.
