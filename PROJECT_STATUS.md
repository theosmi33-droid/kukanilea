# Project Status

## GOALS
- Local-first office assistant with deterministic tool routing.
- Tenant-scoped indexing/search with rebuild tooling.
- DEV controls for DB switching + LLM checks.

## PLANNED
- Add connector module stubs (mail/calendar/messaging) with feature flags.
- Expand task tooling inside chat (list/resolve).
- Add richer document summarization UI.

## DONE
- Spec-first contracts (/contracts) and ADRs (/docs/adr) created for enterprise core.
- Added Constitution, threat model, and phase-1 spec/plan docs.
- Standardized API error envelopes, request-id correlation, and CSRF hardening.
- Chat UI now includes retries/backoff, safe mode toggle, explain-why panel, and task creation.
- Added rate limits, chat history persistence, and expanded smoke/integration tests.
- Added local-first time tracking (projects/entries) with CSV export.

## TODO
- Add role-based task list + resolution actions in chat.
- Add more structured customer summaries (entities view).

## How to test
1) Seed dev users:
   - Command: `python scripts/seed_dev_users.py`
   - Expect: "Seeded users" message in stdout.
2) Start app:
   - Command: `python kukanilea_app.py`
   - Expect: server starts, login with dev/dev works.
3) Chat checks (DEV or ADMIN login):
   - "rechnung" → returns search guidance/results.
   - "wer ist 12393" → returns customer lookup result.
   - "suche angebot von gerd" → returns results or fuzzy suggestion.
   - "öffne <token>" → returns open action link.
4) DEV Settings:
   - Navigate to /settings as dev → shows DB info.
   - Switch DB from allowlist → audit logged, page reloads.
   - Switch Ablage path → audit logged, page reloads.
   - Rebuild index → status updates.
   - Repair drift scan → status updates.
   - Test LLM → returns provider name and intent.
