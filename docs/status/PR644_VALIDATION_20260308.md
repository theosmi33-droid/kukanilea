# PR644 Validation

## Change
- Enforce quota and throttling on upload ingest endpoint.

## Local Tests
- `PYENV_VERSION=3.12.0 python -m pytest -q tests/contracts/test_upload_ingestion_contracts.py tests/test_upload_ingestion_parser.py`

## Result
- 10 tests passed.

