# PR643 Validation

## Change
- Enforce attachment size and tenant quota during IMAP ingest.

## Local Tests
- `PYENV_VERSION=3.12.0 python -m pytest -q app/mail/test_postfach_domain.py`
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/security/test_mail_attachment_quota_guard.py tests/integration/test_mail_ingest_attachment_quota_contract.py`

## Result
- All targeted tests passed.

