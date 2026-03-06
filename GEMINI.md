# KUKANILEA Gemini Workspace Instructions

Read and follow these files before any implementation:

1. /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/AI_AGENT_OPERATING_CONTRACT.md
2. /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_REFERENCE_STACK.md
3. /Users/gensuminguyen/Kukanilea/kukanilea_production/app/agents/config/AGENTS.md

Rules:
- Keep changes scoped to this workspace/domain.
- No destructive git operations.
- Run healthcheck/tests and report PASS/FAIL with evidence.
- Main-only policy:
  - `main` is the single source of truth.
  - Every PR must target `main`.
  - Always sync from `origin/main` before starting work.
  - Never base new work on stale feature branches.
