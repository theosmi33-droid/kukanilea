Mode: REVIEW_ONLY (strict). Do not edit files. Do not run destructive git commands.
Return only the final report. Do not print step-by-step intentions.

Mission:
- Follow `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_MISSION_BRIEF.md`.
- If anything is unclear, output `NEEDS_CODEX` and stop.

Task:
1) Build overlap matrix for exactly these 11 worktrees:
   - /Users/gensuminguyen/Kukanilea/worktrees/dashboard
   - /Users/gensuminguyen/Kukanilea/worktrees/upload
   - /Users/gensuminguyen/Kukanilea/worktrees/emailpostfach
   - /Users/gensuminguyen/Kukanilea/worktrees/messenger
   - /Users/gensuminguyen/Kukanilea/worktrees/kalender
   - /Users/gensuminguyen/Kukanilea/worktrees/aufgaben
   - /Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung
   - /Users/gensuminguyen/Kukanilea/worktrees/projekte
   - /Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer
   - /Users/gensuminguyen/Kukanilea/worktrees/einstellungen
   - /Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot
   Use `git -C <worktree> diff --name-only main...HEAD` as source for files.
2) Focus on `dashboard` and `projekte` if still failing.
3) For each failing domain, provide exact safe Codex commands only (no execution) to:
   - extract shared-core diff into scope-request patch/markdown,
   - remove shared-core file from domain branch while preserving domain files,
   - re-check overlap.
4) Stop after final matrix + command plan.

Output format:
- Status
- Before matrix
- Safe command plan per failing domain
- After matrix (expected)
- NEEDS_CODEX: yes/no
