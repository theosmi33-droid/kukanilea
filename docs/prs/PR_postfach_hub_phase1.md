## Summary
- Replaced legacy "Mail" tab with a new tenant-scoped **Postfach Hub** (`/postfach`) for account management, thread view, drafting, and controlled sending.
- Added mailbox data model (`mailbox_accounts`, `mailbox_threads`, `mailbox_messages`, `mailbox_attachments`, `mailbox_drafts`, `mailbox_links`) with TEXT IDs and idempotent schema creation.
- Implemented secure IMAP sync and SMTP send connectors with server-side confirmation gate and fail-closed secret handling.
- Added Postfach tool-layer functions to the agent tool registry.
- Added dedicated Postfach templates and tests (IMAP, SMTP, web routes, tool contracts).

## Why
- Existing Mail functionality was a minimal v0 and did not provide a central communication hub.
- Phase 1 establishes a practical inbox/thread/action workflow aligned with CRM/task operations while preserving offline-first and core-freeze constraints.

## Scope
- `app/mail/postfach_store.py`
  - schema + persistence + encrypted secrets + redaction-first storage + eventlog entries without PII
- `app/mail/postfach_imap.py`
  - IMAP4_SSL sync, dedupe, threading (`Message-ID`, `In-Reply-To`, `References`), redacted persistence
- `app/mail/postfach_smtp.py`
  - SMTP send with `user_confirmed` enforcement, sent-message persistence
- `app/web.py`
  - `/postfach` routes, `/mail` redirect compatibility, actions: sync, draft, send, link entities, extract, follow-up, lead creation
- `app/agents/tools.py`
  - postfach tools: sync/list/get/draft/send/link/extract/follow-up
- `templates/postfach/*`
  - index/thread/compose views
- Tests
  - `tests/test_postfach_imap.py`
  - `tests/test_postfach_smtp.py`
  - `tests/test_postfach_web.py`
  - `tests/test_agents_tools.py` (extended)

## Verification
- [x] python -m compileall -q .
- [x] ruff check .
- [x] ruff format . --check
- [x] pytest -q
- [x] python -m app.devtools.security_scan
- [x] python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
- [x] python -m app.devtools.schema_audit --json > /dev/null

## Security / Compliance
- [x] No PII in eventlog payloads (IDs/counts only in Postfach events)
- [x] Secrets never stored in plaintext (`encrypted_secret`, fail-closed if `EMAIL_ENCRYPTION_KEY` missing)
- [x] IMAP enforced via `IMAP4_SSL(..., ssl_context=ssl.create_default_context())`
- [x] SMTP send is blocked unless `user_confirmed=true` is provided server-side
- [x] READ_ONLY guard enforced for all mutating Postfach routes

## Review Checklist
- [x] I completed `docs/PR_REVIEW_CHECKLIST.md`

## Rollout / Rollback
- Rollout:
  - Deploy as additive feature; `/mail` keeps compatibility via redirect to `/postfach`.
- Rollback:
  - Revert this PR commit; existing legacy mail modules remain available in history.

## Out of Scope
- OAuth2 provider flows (Gmail/MS Graph)
- Async/background sync workers
- Global TEXT-ID migration of legacy tables
