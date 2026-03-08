# PR643 Security Review

## Scope
- IMAP ingest attachment size enforcement
- tenant quota enforcement for stored attachment payloads

## Findings
- Oversized attachments are rejected with explicit reason (`file_too_large`).
- Quota overflow attachments are rejected with explicit reason (`tenant_quota_exceeded`).
- Existing domain tests plus new security/contract tests cover both rejection paths.

