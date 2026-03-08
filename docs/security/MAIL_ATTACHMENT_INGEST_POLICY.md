# Mail Attachment Ingest Policy

Date: 2026-03-08

## Controls
- Enforce per-tenant attachment quota before accepting attachment payloads.
- Reject attachments larger than configured file-size ceiling.
- Persist rejection status with a structured reason for audit/debug visibility.

## Validation
- `app/mail/test_postfach_domain.py`
- `tests/security/test_mail_attachment_quota_guard.py`
- `tests/integration/test_mail_ingest_attachment_quota_contract.py`

