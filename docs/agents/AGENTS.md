# KUKANILEA MIA Agent Framework

This framework defines a deterministic, offline-first, and approval-gated agent architecture for KUKANILEA.

## Agent Roles

### Orchestrators (The Core)
- **ROUTER:** Directs user requests to the appropriate domain worker or triage.
- **SCHEDULER:** Manages task execution order and timing, ensuring no overlaps or conflicts.
- **TRIAGE:** Handles errors, edge cases, and requests that don't fit into standard domains.

### Domain Workers (The Hands)
1.  **AUTH_BOT:** Manages user sessions, permissions, and identity.
2.  **DB_BOT:** Handles SQL migrations and data integrity checks.
3.  **MAIL_BOT:** Manages encrypted local mail queues.
4.  **LOG_BOT:** Analyzes system logs for anomalies.
5.  **NET_BOT:** Verwaltet lokale Netzwerkpfade local-first, offline-first und auditierbar.
6.  **SEC_BOT:** Performs static security analysis and vulnerability scanning.
7.  **DEPLOY_BOT:** Manages local-first builds and releases.
8.  **SYNC_BOT:** Orchestrates peer-to-peer data synchronization.
9.  **AI_BOT:** Führt MIA-Inferenz im Sovereign-11 Pfad lokal, offline-first und auditierbar aus.
10. **FILES_BOT:** Manages file system operations and provenance.
11. **DOCS_BOT:** Maintains project documentation and ADRs.

### Safeguards
- **CANARY:** Runs a shadow version of tasks to detect regressions before they hit production.
- **OBSERVER:** The ultimate gatekeeper. Logs every action: `BLOCKED`, `CONFIRM_REQUIRED`, `EXECUTED`.

## Approval Mechanism
- **GATED WRITES:** Any action that modifies state (FS, DB, NET) requires an explicit `User Approval`.
- **OBSERVER LOG:** All gated actions are streamed to a local audit log for visibility.

## Memory Policy
- **TENANT SCOPED:** Memory never leaks between tenants.
- **60-DAY RETENTION:** Default history retention is 60 days.
- **CLEANUP:** Weekly scheduled jobs prune expired state.

## Branch Policy (Main-Only)
- **SINGLE SOURCE:** `main` is the only source of truth.
- **PR TARGET:** All pull requests must target `main`.
- **SYNC FIRST:** Start work from latest `origin/main`.
- **NO FEATURE CHAINING:** Do not stack new work on old feature branches.
