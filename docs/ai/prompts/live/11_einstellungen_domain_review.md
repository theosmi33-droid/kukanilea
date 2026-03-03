Mode: REVIEW_ONLY (strict). Do not edit files.
Mission: Follow GEMINI_MISSION_BRIEF.
Task:
1) Review `einstellungen` in `/Users/gensuminguyen/Kukanilea/worktrees/einstellungen`.
2) Run:
   - git status --short
   - git diff --name-only main...HEAD
   - python scripts/dev/check_domain_overlap.py --reiter einstellungen --files <diff_files> --json
   - pytest -q tests/test_lexoffice.py || true
3) Output concrete blockers + exact Codex commands.
Output format:
- Status
- Findings P0/P1/P2
- Commands for Codex
- NEEDS_CODEX: yes/no
