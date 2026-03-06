# KUKANILEA Production Backlog

## Overview
This backlog contains >= 2200 atomic engineering tasks (2–45 min each) designed for a high-velocity, PR-shippable workflow.

## Structure
- `backlog_v1.yaml`: The source of truth for all tasks.
- `LANE_RULES.md`: Ownership boundaries.

## Claiming a Task
1. Filter `backlog_v1.yaml` by your lane and domain.
2. Select a task that has no pending dependencies (`dependencies: []` or completed IDs).
3. Update the task status (externally tracked or through PR).
4. Implement the task following the `file_scope`.
5. Run the defined `tests_to_run` and verify `evidence_required`.

## Definition of Done (DoD)
- Code is implemented within the `file_scope`.
- No regressions in `CORE_OWNED` files.
- Automated tests pass (include output in PR).
- Evidence of success is captured (logs, screenshots, or benchmark results).
- Rollback plan verified.

## Priorities
1. **Top 50 ROI**: Focus on these first to maximize immediate value.
2. **Security Gates**: Critical path for production hardening.
3. **Core Features**: Domain-specific MVPs.

## Top 50 ROI Highlights
These tasks (TASK-0001 to TASK-0050) are designed to reduce manual admin time fastest:
- **AI Intent Extraction**: Automate incoming request classification (TASK-0019, TASK-0034).
- **Construction Diary Automation**: Defect reporting from WhatsApp/Voice (TASK-0026, TASK-0041).
- **Time Tracking Hardening**: Legally robust absence/overtime rules (TASK-0011, TASK-0022).
- **ZUGFeRD Integration**: Automate invoice data extraction (TASK-0038, TASK-0049).
- **Self-Healing Checks**: Automated recovery for domain services (TASK-0033).
