# PR637 Validation

## Change
- Bound idempotency cache growth.

## Local Tests
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/test_idempotency_store.py`

## Result
- Targeted tests passed.

