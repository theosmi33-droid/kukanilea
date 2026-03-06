# KUKANILEA MIA-Agentenflotte

Diese Konfiguration definiert das KUKANILEA-eigene MIA-Agentenframework.
It is deterministic, offline-first, and approval-gated.

## 1. Orchestrators (The Core)
1. **ORCH-ROUTER**: Routes tasks based on domain metadata.
2. **ORCH-SCHEDULER**: Manages execution queues and timing.
3. **ORCH-TRIAGE**: Handles errors, retries, and manual overrides.

## 2. Domain Workers (The Hands)
1. **WRK-AUTH_BOT**: Session, permissions, identity management.
2. **WRK-DB_BOT**: SQL migrations, data integrity checks.
3. **WRK-MAIL_BOT**: Local encrypted mail queue.
4. **WRK-LOG_BOT**: System log anomaly detection.
5. **WRK-NET_BOT**: Local-first Netzwerkpfade, offline-first Synchronisation, auditierbar.
6. **WRK-SEC_BOT**: Static security & vulnerability scanning.
7. **WRK-DEPLOY_BOT**: Local-first builds and releases.
8. **WRK-SYNC_BOT**: Peer-to-peer data synchronization.
9. **WRK-AI_BOT**: MIA-Inferenz im Sovereign-11 Laufzeitpfad (lokal, offline-first, auditierbar).
10. **WRK-FILES_BOT**: File system operations & provenance.
11. **WRK-DOCS_BOT**: Project documentation and ADR maintenance.

## 3. Safeguards
1. **SAFE-CANARY**: Shadow execution for regression detection.
2. **SAFE-OBSERVER**: Passive audit logging and gatekeeping.

## 4. Approval Gates (Mandatory)
- **LEVEL 1 (READ-ONLY)**: No approval.
- **LEVEL 2 (VOLATILE)**: Warning for large reads.
- **LEVEL 3 (MODIFICATION)**: Mandatory confirmation.
- **LEVEL 4 (DESTRUCTIVE)**: Double confirmation.

## 5. Memory Policy
- **TENANT SCOPED**: Strict isolation.
- **60-DAY RETENTION**: Automatic pruning of task history.
- **CLEANUP JOB**: `scripts/ops/memory_cleanup.py`.

## 6. Branch Policy (Main-Only)
- **SINGLE SOURCE**: `main` is the only source of truth.
- **PR TARGET:** All pull requests must target `main`.
- **SYNC FIRST:** Start work from latest `origin/main`.
- **NO FEATURE CHAINING:** Do not stack new work on old feature branches.
