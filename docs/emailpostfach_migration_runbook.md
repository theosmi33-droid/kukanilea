# Emailpostfach Agent — Migration Notes + Runbook

## Migration notes

The Emailpostfach agent introduces three new SQLite tables inside `AuthDB.init()`:

1. `emailpostfach_messages`
   - Stores ingested inbound messages from provider adapters (IMAP/POP/SMTP intake stubs).
   - Key uniqueness: `(tenant_id, provider, provider_message_id)`.
2. `emailpostfach_drafts`
   - Stores generated/editable drafts with mandatory confirm-gate fields.
3. `emailpostfach_audit`
   - Immutable append-style audit trail for sync, draft edits, and send actions.

Additionally, two indexes are created:
- `idx_emailpostfach_messages_tenant_unread`
- `idx_emailpostfach_audit_tenant_action_ts`

### Operational impact
- No destructive migration is required.
- Existing deployments auto-create missing tables at app start when `AuthDB.init()` runs.
- Backward compatible: older code paths are unaffected.

## Runbook

### 1) Ingest emails (provider architecture with stubs)

```bash
curl -X POST http://localhost:5000/api/emailpostfach/ingest \
  -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <token>' \
  -b 'session=<cookie>' \
  -d '{"provider":"imap_stub","actor":"admin"}'
```

Supported provider values in current stub implementation:
- `imap_stub` / `imap`
- `pop_stub` / `pop` / `pop3`
- `smtp_stub` / `smtp_intake`

Failure simulation:
- `auth_fail` → HTTP 401
- `network_fail` → HTTP 503

### 2) Read emailpostfach summary

```bash
curl -X GET http://localhost:5000/api/emailpostfach/summary -b 'session=<cookie>'
```

Contract highlights:
- `metrics.unread_count`
- `metrics.follow_ups_due`
- `last_sync`

### 3) Generate deterministic draft fallback

```bash
curl -X POST http://localhost:5000/api/emailpostfach/draft/generate \
  -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <token>' \
  -b 'session=<cookie>' \
  -d '{"actor":"admin","message":{"subject":"Dringend","from":"kunde@example.com"}}'
```

Notes:
- Uses deterministic templates by default.
- `use_llm=true` is supported by architecture; currently falls back unless an LLM generator is wired in.

### 4) Edit draft (audited)

```bash
curl -X POST http://localhost:5000/api/emailpostfach/draft/<draft_id>/edit \
  -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <token>' \
  -b 'session=<cookie>' \
  -d '{"actor":"admin","subject":"Updated","body":"Updated body"}'
```

### 5) Send draft with confirm-gate (audited)

Blocked (expected 409):
```bash
curl -X POST http://localhost:5000/api/emailpostfach/draft/<draft_id>/send \
  -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <token>' \
  -b 'session=<cookie>' \
  -d '{"actor":"admin","confirm":"no"}'
```

Allowed (expected 200):
```bash
curl -X POST http://localhost:5000/api/emailpostfach/draft/<draft_id>/send \
  -H 'Content-Type: application/json' \
  -H 'X-CSRF-Token: <token>' \
  -b 'session=<cookie>' \
  -d '{"actor":"admin","confirm":"yes"}'
```

Audit actions written to `emailpostfach_audit`:
- `emailpostfach.sync`
- `emailpostfach.draft.edit`
- `emailpostfach.send`
