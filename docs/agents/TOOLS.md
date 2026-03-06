# TOOL SAFETY AND CAPABILITIES

## Approved Tools
- **FILE OPS:** `read_file`, `write_file`, `replace`, `glob`, `grep_search`.
- **SYSTEM:** `run_shell_command` (limited to white-listed commands).
- **ORCHESTRATION:** `task_delegation`, `result_aggregation`.

## Prohibited Actions
- **NO REMOTE:** Calling external APIs directly from agents (must go through SYNC_BOT).
- **NO SECRET LEAKAGE:** Printing `.env` files or secrets to any log or output.
- **NO UNSAFE SHELL:** Pipes (`|`) or redirects (`>`) in user-input-derived commands without sanitization.

## Safe Addition Guide
1.  **Define Tool Capability:** Is it read or write?
2.  **Assign Level:** Level 1, 2, 3, or 4?
3.  **Implement Guard:** Add to `kukanilea/guards.py`.
4.  **Test in Canary:** Verify logic and safety.
