# Evidence Drill Sample (License + Backup/Restore)

## License status
- status: `OK|WARN|LOCKED`
- grace policy: `LICENSE_GRACE_DAYS` days after `valid_until`/`last_verified_at`
- fail-closed: `LOCKED` always maps to NO-GO in launch gate

Example:
```
status=OK:VALID
status=WARN:GRACE
status=LOCKED:EXPIRED
```

## Backup evidence (tenant separated)
```
report_version=1
mode=degraded_local
tenant_id=DEMO_TENANT
backup_file=DEMO_TENANT_2026-03-05_10-15.tar.zst
target_path=instance/degraded_backups/DEMO_TENANT/DEMO_TENANT_2026-03-05_10-15.tar.zst
checksum_sha256=2f79...
source_size_bytes=110592
backup_size_bytes=9231
compression_ratio=0.0835
checksum_file=instance/degraded_backups/DEMO_TENANT/DEMO_TENANT_2026-03-05_10-15.tar.zst.sha256
```

## Restore evidence (staging verify + measured time)
```
report_version=1
mode=degraded_local
tenant_id=DEMO_TENANT
backup_file=DEMO_TENANT_2026-03-05_10-15.tar.zst
verify_db=ok
verify_files=ok
restore_validation=ok
rto_seconds=3
rpo_seconds=120
```

## Rollback plan
1. Stop app service.
2. Restore previous known-good archive for same tenant.
3. Re-run `scripts/ops/restore_from_nas.sh` with explicit `BACKUP_FILE`.
4. Verify `verify_db=ok`, `verify_files=ok`, `restore_validation=ok`.
5. Re-enable traffic after healthcheck is green.
