Mode: REVIEW_ONLY (strict). Do not edit files.

Mission:
- Follow `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_MISSION_BRIEF.md`.

Task:
1) Review domain `aufgaben` in `/Users/gensuminguyen/Kukanilea/worktrees/aufgaben`.
2) Run these checks:
   - `git -C /Users/gensuminguyen/Kukanilea/worktrees/aufgaben status --short`
   - `git -C /Users/gensuminguyen/Kukanilea/worktrees/aufgaben diff --name-only main...HEAD`
   - `cd /Users/gensuminguyen/Kukanilea/worktrees/aufgaben && pytest -q tests/domains/aufgaben || true`
   - `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter aufgaben --files $(git -C /Users/gensuminguyen/Kukanilea/worktrees/aufgaben diff --name-only main...HEAD) --json || true`
3) Pay special attention to separation from `projekte` (Kanban ownership boundary).
4) Classify findings into P0/P1/P2 and provide exact Codex commands (no execution).

Output format:
- Status
- Findings P0/P1/P2
- Commands for Codex
- NEEDS_CODEX: yes/no
