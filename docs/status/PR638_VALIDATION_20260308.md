# PR638 Validation (Tar extraction hardening)

## Changed
- Hardened tar extraction to block traversal and unsafe entry classes.
- Added security-focused regression tests for symlink/hardlink/absolute/traversal entries.
- Added integration contract test for safe tarball application path.

## Local Validation
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/test_inplace_update.py`
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/security/test_inplace_update_archive_hardening.py`
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/integration/test_inplace_update_tarball_contract.py`

