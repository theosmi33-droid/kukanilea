Mode: REVIEW_ONLY (strict). Do not edit files.

Mission:
- Follow `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_MISSION_BRIEF.md`.

Task:
1) Review domain `upload` in `/Users/gensuminguyen/Kukanilea/worktrees/upload`.
2) Run these checks:
   - `git -C /Users/gensuminguyen/Kukanilea/worktrees/upload status --short`
   - `git -C /Users/gensuminguyen/Kukanilea/worktrees/upload diff --name-only main...HEAD`
   - `cd /Users/gensuminguyen/Kukanilea/worktrees/upload && pytest -q tests/domains/upload || true`
   - `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter upload --files $(git -C /Users/gensuminguyen/Kukanilea/worktrees/upload diff --name-only main...HEAD) --json || true`
3) Classify findings into P0/P1/P2 and provide exact Codex commands (no execution) to fix only concrete issues.
4) Keep strict scope: no file edits.

Output format:
- Status
- Findings P0/P1/P2
- Commands for Codex
- NEEDS_CODEX: yes/no
