# Project Status

## GOALS
- Local-first office assistant with deterministic tool routing.
- Tenant-scoped indexing/search with rebuild tooling.
- DEV controls for DB switching + LLM checks.
- Phase 2 product core: time tracking, jobs/tasks, hardened intake.

## PLANNED
- Phase 2.1: Work time tracking (projects, timers, approvals, export).
- Phase 2.2: Jobs/projects/tasks core with due dates + assignees.
- Phase 2.3: Document intake → review → archive hardening.

## DONE
- Spec-first contracts (/contracts) and ADRs (/docs/adr) created for enterprise core.
- Chat API returns structured JSON with suggestions, results, and actions; UI shows tool actions and quick suggestions.
- Intent parsing expanded for short queries, KDNR-only, and “wer ist <kdnr>” routing.
- Search ranking improved (KDNR, name similarity, doctype match, recency) with deterministic fallback + fuzzy suggestions.
- DEV Settings page includes DB/base-path switching, rebuild index, and drift scan actions.
- Ollama provider gated by feature flag with deterministic fallback.
- Prompt injection guardrails + regression tests for blocked prompts.
- Phase 2 spec + ADR for time tracking created.
- PR1 started: re-extract path resolution now uses allowlisted DB fallback (`versions.file_path`) with deterministic `source_not_found` metadata and audit events (`reextract_ok` / `reextract_failed`).

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
