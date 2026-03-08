# In-Place Update Archive Safety Policy

Date: 2026-03-08  
Scope: `app/core/inplace_update.py`

## Rules
- Archive extraction is fail-closed.
- Tar members with absolute paths or traversal (`..`) are rejected.
- Symlinks, hardlinks, and device entries are rejected.
- Extracted targets must resolve under the temporary extraction root.

## Regression Coverage
- `tests/test_inplace_update.py`
- `tests/security/test_inplace_update_archive_hardening.py`
- `tests/integration/test_inplace_update_tarball_contract.py`

