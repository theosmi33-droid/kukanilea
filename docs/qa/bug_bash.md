# Phase 2 Bug Bash Plan

## Objective
Run a focused cross-functional bug bash before beta.

## Timebox
- Duration: 90 minutes
- Window: within 3 days after Phase 2 PR opens

## Roles
- Facilitator: tracks agenda and bug triage
- Engineers: reproduce/fix high severity findings
- Product: validates UX and acceptance criteria

## Severity Rules
- `critical`: data loss, auth bypass, tenant leak, system crash
- `high`: core flow broken with no workaround
- `medium`: degraded behavior with workaround
- `low`: cosmetic or copy issue

## Execution Flow
1. Assign each participant one primary area: CRM, Tasks, Workflows, AI, Mail.
2. Log every finding as GitHub issue with labels: `bug`, `qa`.
3. Add `critical` label immediately when severity qualifies.
4. Triage at the 45-minute mark and at end.

## Exit Criteria
- No open `critical` issues.
- All `high` issues have owner and fix plan.
- Repro steps documented for each issue.
