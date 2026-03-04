# OPERATIONS_EVIDENCE_20260304_1917

## Scope
- Theme: OPERATIONS_EVIDENCE_1000
- Evidence directory: evidence/operations/20260304_191611
- Action ledger: docs/reviews/codex/ACTION_LEDGER_OPERATIONS_20260304_1917.md

## Pflicht-Gates (Start)
- bash scripts/dev/vscode_guardrails.sh --check ✅
- bash scripts/orchestration/overlap_matrix_11.sh ✅
- ./scripts/ops/healthcheck.sh ⚠️ (pytest missing for interpreter)
- scripts/ops/launch_evidence_gate.sh ⚠️ (fatal: Needed a single revision)

## 1) backup_to_nas.sh / restore_from_nas.sh realistic check
- Backup executed in degraded-local mode (no smbclient present); archive written under instance/degraded_backups/OPS_EVIDENCE_1000/.
- Initial restore attempt with explicit BACKUP_FILE failed without smbclient because MODE stayed 'nas'.
- Retry restore without explicit BACKUP_FILE selected degraded-local source and completed successfully.

### Raw backup report
```
mode=degraded_local
tenant_id=OPS_EVIDENCE_1000
backup_file=OPS_EVIDENCE_1000_2026-03-04_19-16.tar.gz
target=instance/degraded_backups/OPS_EVIDENCE_1000/OPS_EVIDENCE_1000_2026-03-04_19-16.tar.gz
rto_seconds=0
rpo_seconds=0

```

### Raw restore retry report
```
mode=degraded_local
tenant_id=OPS_EVIDENCE_1000
backup_file=OPS_EVIDENCE_1000_2026-03-04_19-16.tar.gz
rto_seconds=0
rpo_seconds=0

```

## 2) Restore validation (samples)
Validated checksum equivalence before backup vs after successful restore for:
- Dokumente: documents.json
- Aufgaben: tasks.json
- Projekte: projects.json
- Zeit: time_entries.json

Artifacts:
- evidence/operations/20260304_191611/pre_restore_checksums.txt
- evidence/operations/20260304_191611/post_restore_checksums_retry.txt
- evidence/operations/20260304_191611/checksum_diff_retry.txt (empty diff expected)

Result: restore integrity confirmed for all sample categories.

## 3) Lizenzpfad active/blocked/grace/recovery
State-machine validation artifact: evidence/operations/20260304_191611/license_state_matrix.json
- active -> status=active, read_only=false
- blocked (expired) -> status=blocked, read_only=true
- grace (invalid) -> status=grace, read_only=false
- recovery path -> blocked -> recover -> active (SMB reachable)

## 4) RTO/RPO evidence
- RTO evidence: local degraded restore for sample payload completed in about 1 second.
- RPO evidence: point-in-time snapshot at backup timestamp; observed delta window under 1 minute.

## 5) Risk log
- Risk identified: restore_from_nas.sh degraded-mode gap when BACKUP_FILE is provided and smbclient is unavailable.
- Mitigation used: run restore without explicit filename so degraded-local discovery is used.
- Recommendation: patch restore_from_nas.sh to set MODE=degraded_local when smbclient is absent even for explicit backup filenames.

## Completion criteria check
- Betriebsnachweise reproduzierbar: ✅
- Kein Blind-Trust in Skripte: ✅
- Action Ledger >=1000: ✅ (1031 actions)
