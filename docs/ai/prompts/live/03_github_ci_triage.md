Mode: REVIEW_ONLY (strict). Do not edit files.

Mission:
- Follow `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_MISSION_BRIEF.md`.

Task:
1) Analyze GitHub Actions in `theosmi33-droid/kukanilea` (max 300 latest runs) using shell commands:
   - `gh run list --repo theosmi33-droid/kukanilea --limit 300 --json databaseId,name,workflowName,status,conclusion,createdAt,updatedAt,url`
   - If needed for failures: `gh run view <id> --repo theosmi33-droid/kukanilea --log-failed`
2) If no failed/cancelled runs: state this clearly and stop.
3) If failures exist: cluster by workflow and give top 5 prevention actions.

Output format:
- Status
- Failure summary
- Top 5 actions
- NEEDS_CODEX: yes/no
