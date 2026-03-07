# KUKANILEA MIA Workspace Instructions

Read and follow these files before any implementation:

1. /Users/gensuminguyen/Kukanilea/docs/ai/AI_AGENT_OPERATING_CONTRACT.md
2. /Users/gensuminguyen/Kukanilea/docs/ai/MIA_REFERENCE_STACK.md
3. /Users/gensuminguyen/Kukanilea/app/agents/config/AGENTS.md

Rules:
- Keep changes scoped to this workspace/domain.
- No destructive git operations.
- Run healthcheck/tests and report PASS/FAIL with evidence.
- Main-only policy:
  - `main` is the single source of truth.
  - Work on `main` only by default.
  - Do not create branches unless the user explicitly asks for a branch-based PR flow.
  - All pull requests must target `main`.
  - Start work from the latest `origin/main`.
  - Do not stack new work on old feature branches.
  - Do not auto-switch branches in helper scripts; fail fast with a clear error instead.
  - For interactive terminal launchers, require a clean working tree before execution.
