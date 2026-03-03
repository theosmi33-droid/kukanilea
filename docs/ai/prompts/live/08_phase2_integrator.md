Mode: REVIEW_ONLY (strict). Do not edit files.

Mission:
- Follow `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_MISSION_BRIEF.md`.

Task:
1) Build a compact Phase-2 integrator report from current repository state:
   - Overlap status across 11 worktrees
   - VSCode guardrails status (`bash /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/vscode_guardrails.sh --check`)
   - GitHub actions status (`gh run list --repo theosmi33-droid/kukanilea --limit 100 --json conclusion,name,status,workflowName`)
2) Output only concrete blockers and next 5 executable Codex steps.
3) No file edits.

Output format:
- Status
- Blockers
- Next 5 Codex steps
- NEEDS_CODEX: yes/no
