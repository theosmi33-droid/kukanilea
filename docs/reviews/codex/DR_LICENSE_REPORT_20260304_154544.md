# DR + License Operations Report (20260304_154544)

## Scope
- Demo data seeding for tenant/business entities.
- Verified backup/restore drill (local NAS simulation, dry-run/real-run capable scripts).
- Restore metric validation (before/after parity).
- License state machine hardening (active / blocked / SMB-down grace / recovery).

## Implemented Artifacts
- scripts/seed_demo_data.py
- scripts/ops/backup_to_nas.sh
- scripts/ops/restore_from_nas.sh
- scripts/ops/restore_validation.py
- tests/ops/test_backup_restore_drill.py
- tests/license/test_license_state_machine.py

## Drill Evidence
1. Seeded demo dataset into auth/core sqlite DBs.
2. Executed backup to NAS target (`evidence/nas/KUKANILEA/...`).
3. Executed restore from latest NAS backup artifact.
4. Compared core metrics before/after restore: no diffs.

## License Failover Validation
- **Active:** normal operations, read/write.
- **SMB-down grace:** transitions to `grace` while within configured grace window.
- **Blocked:** transitions to `blocked` + read-only after grace expiry when SMB remains unavailable.
- **Recovery:** transitions back to `active` when SMB availability resumes.

## Test Matrix
- `PYENV_VERSION=3.12.12 pytest -q tests/ops tests/license` => **2 passed**

## Notes
- Environment default `python`/`pytest` failed because `.python-version` pins unavailable `3.12.0`; execution used `PYENV_VERSION=3.12.12` override for verification.
