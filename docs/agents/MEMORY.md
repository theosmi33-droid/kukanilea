# AGENT MEMORY AND PERSISTENCE

## Memory Structure
- **SHORT-TERM:** Per-task execution context (cleared on completion).
- **LONG-TERM:** Learned behaviors and project context (stored in `MEMORY.md`).

## Retention Policy
- **DEFAULT:** 60 days.
- **CRITICAL:** Permanent (requires manual flag).
- **LOGS:** 30 days.

## Cleanup Job
`scripts/ops/memory_cleanup.py` runs every Sunday at 02:00 to prune expired records.
