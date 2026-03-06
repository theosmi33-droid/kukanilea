# THE USER: THE ULTIMATE GATEKEEPER

## Interaction Rules
1.  **CONFIRMATION:** Any operation that modifies the filesystem, database, or network requires a "Gated Confirmation."
2.  **CONCISE RESPONSES:** Agents should provide high-signal information and avoid conversational filler.
3.  **FEEDBACK LOOP:** Users provide feedback that is stored in the agent's `MEMORY.md` to improve performance.

## Approval Levels
- **LEVEL 1 (READ-ONLY):** No approval required (e.g., `grep`, `ls`).
- **LEVEL 2 (VOLATILE):** Optional approval for large reads or complex queries.
- **LEVEL 3 (MODIFICATION):** Mandatory approval for all writes (e.g., `write_file`, `git commit`).
- **LEVEL 4 (DESTRUCTIVE):** Double confirmation for deletes (e.g., `rm`, `drop table`).
