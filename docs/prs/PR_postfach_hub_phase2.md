## Title
feat(postfach): phase 2 oauth-ready inbox hub, intake pipeline, and guarded send flow

## Why
Phase 2 extends the Postfach hub from phase 1 into a workflow intake surface:
- OAuth-ready account connection for Google and Microsoft providers.
- Encrypted token handling with fail-closed behavior.
- Structured intake extraction from threads.
- Guarded draft sending with mandatory user confirmation and safety acknowledgement.

## Scope
### OAuth layer
- Added PKCE helpers, provider config, authorization URL builder, token exchange, token refresh, and XOAUTH2 auth-string helper.
- Added config keys for Microsoft OAuth and optional redirect base.

### Store/schema
- Added mailbox OAuth token table and intake artifact table.
- Extended mailbox account sync state/status fields.
- Added encrypted OAuth token storage and retrieval helpers.
- Added intake extraction artifact persistence and draft safety-check logic.

### Connectors
- IMAP connector supports password and OAuth/XOAUTH2 modes.
- SMTP connector supports password and OAuth/XOAUTH2 modes.
- Sync/report fields are updated on success/error paths.
- Retry/backoff for fetch failures in IMAP sync.

### Web/UI
- OAuth routes: start, callback, disconnect.
- Account form supports auth-mode/provider selection.
- Thread actions: intake, lead, case, tasks, follow-up, linking.
- Send flow requires `user_confirmed` and enforces safety acknowledgement if warnings exist.

### Agents
- Added postfach intake/lead/case/task tools and dot-aliases for orchestrator compatibility.

### Tests
- Added OAuth helper unit tests.
- Extended IMAP/SMTP tests for OAuth paths.
- Extended web tests for OAuth callback/session flow and safety-ack send gating.

## Security notes
- TLS-only mail transport remains enforced.
- No plaintext secrets/tokens persisted.
- Missing `EMAIL_ENCRYPTION_KEY` fails closed for mail operations.
- Event payloads stay ID/metric focused.

## How to verify
```bash
python -m compileall -q .
ruff check .
ruff format . --check
pytest -q
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
python -m app.devtools.schema_audit --json > /dev/null
```

## Out of scope
- No new dependencies.
- No global TEXT-ID migration.
- No claim of compliance certifications beyond current deployment capabilities.

## Risks and rollback
- Changes are split into atomic commits by layer for selective revert.
- Schema changes are additive (`IF NOT EXISTS` + additive columns).
