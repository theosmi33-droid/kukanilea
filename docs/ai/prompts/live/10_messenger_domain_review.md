Mode: REVIEW_ONLY (strict). Do not edit files.
Mission: Follow GEMINI_MISSION_BRIEF.
Task:
1) Review `messenger` in `/Users/gensuminguyen/Kukanilea/worktrees/messenger`.
2) Run:
   - git status --short
   - git diff --name-only main...HEAD
   - python scripts/dev/check_domain_overlap.py --reiter messenger --files <diff_files> --json
   - pytest -q tests/test_tool_runtime.py || true
3) Output concrete blockers + exact Codex commands.
Output format:
- Status
- Findings P0/P1/P2
- Commands for Codex
- NEEDS_CODEX: yes/no
