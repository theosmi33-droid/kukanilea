Mode: REVIEW_ONLY (strict). Do not edit files. Do not commit. Do not push.

Task:
- Analyze GitHub Actions for repo theosmi33-droid/kukanilea.
- Scope limit: inspect at most 300 latest runs.
- If failed/cancelled count is 0 in that scope, stop immediately and report "No failures found in latest 300 runs".
- If failures exist: cluster by workflow and list top causes with run URLs.

Output format:
- Status: PASS | PASS with notes | FAIL
- Executive Summary (max 5 lines)
- Cluster table
- Top 10 actions
- VS Code/CI automation steps (max 5)
