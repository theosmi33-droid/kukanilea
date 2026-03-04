# OPERATIONS HARD EVIDENCE FINAL — 20260304_203550

## Scope
MISSION: OPERATIONS_HARD_EVIDENCE_1000

## 1) Backup-to-NAS + degraded fallback
- Script `scripts/ops/backup_to_nas.sh` hardened with:
  - NAS upload retries (`NAS_RETRIES`).
  - SHA-256 checksum generation for each archive.
  - `.sha256` sidecar upload/copy for NAS and degraded-local targets.
  - report fields: `checksum_sha256`, `checksum_file`, `backup_started_epoch`, `backup_completed_epoch`, `rto_seconds`, `rpo_seconds`.
- Evidence:
  - `instance/operator_report_backup_20260304_203550.txt`
  - degraded-local artifact in `instance/degraded_backups/DEMO_TENANT/`

## 2) Restore process with data checksums + sampled business entities
- Script `scripts/ops/restore_from_nas.sh` hardened with:
  - NAS download retries (`NAS_RETRIES`).
  - checksum verification from sidecar (`.sha256`) before extraction.
  - robust fallback to degraded-local when SMB client is unavailable.
  - post-restore validator invocation and status capture.
- Validator `scripts/ops/restore_validation.py` extended with:
  - sampled business-entity stubs for core tables.
  - cross-table `_business_entities_checksum` consistency check.
- Evidence:
  - `evidence/operations/restore_before_20260304_203550.json`
  - `evidence/operations/restore_after_20260304_203550.json`
  - `instance/operator_report_restore_20260304_203550.txt`

## 3) License states active/locked/grace/recovery
- Added/extended tests in `tests/license/test_license_state_machine.py`:
  - alias normalization checks for `locked` and `recovery`.
  - transitions for locked->recover and recovery->active.
- Runtime evidence matrix captured in:
  - `evidence/operations/license_states_20260304_203550.json`

## 4) RTO/RPO measurable KPIs
- Backup report captured:
  - `rto_seconds=0`
  - `rpo_seconds=111`
- Restore report captured:
  - `rto_seconds=3`
  - `rpo_seconds=75`
- Note: values represent local run in this environment and include degraded-local fallback path.

## 5) Launch-Evidence automated refresh
- Executed:
  - `scripts/ops/launch_evidence_gate.sh --fast`
- Generated:
  - `docs/reviews/codex/LAUNCH_EVIDENCE_RUN_20260304_203823.md`
  - `docs/reviews/codex/LAUNCH_DECISION_20260304_203823.md`

## 6) Action Ledger >=1000
- Generated:
  - `docs/reviews/codex/ACTION_LEDGER_OPERATIONS_HARD_EVIDENCE_20260304_203550.md`
- Count:
  - 1001 entries.

## 7) Risks / Open points
- Pytest execution in this container is blocked by missing runtime dependencies (`pytest`/`flask` under configured python toolchain).
- NAS path could not be exercised directly due missing `smbclient`; degraded-local path evidence was collected successfully.
