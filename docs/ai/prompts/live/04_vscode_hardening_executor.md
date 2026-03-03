Mode: REVIEW_ONLY (strict). Do not edit files.

Mission:
- Follow `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_MISSION_BRIEF.md`.

Task:
1) Validate VS Code interpreter/debug settings across core + 11 worktrees by running:
   - `cd /Users/gensuminguyen/Kukanilea/kukanilea_production`
   - `bash ./scripts/dev/vscode_guardrails.sh --check`
2) If drift found, provide exact Codex fix commands only (no execution):
   - `bash ./scripts/dev/vscode_guardrails.sh --apply --install-hooks`
3) Re-run check command and include final validation result.
4) Keep strict REVIEW_ONLY: no file edits.

Output format:
- Drift detected
- Codex fix commands (if needed)
- Final validation status
- NEEDS_CODEX: yes/no
