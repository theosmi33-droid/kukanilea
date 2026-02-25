# Contributing

## Core rules
- Keep changes additive and tenant-safe.
- Keep all security and compliance checks green before merge.
- Update docs for behavioral changes.

## NEVER DO
- Introduce new dependencies without an ADR in `docs/adr/ADR-*.md`.
- Store raw PII in event logs.
- Use `subprocess` with `shell=True`.
- Ship mutating endpoints without READ_ONLY guard.
- Merge changes that bypass tenant scoping.

## ALWAYS DO
- Use deterministic error envelopes for API failures.
- Use `secrets.compare_digest()` for token/code/hash comparisons.
- Redact OCR/mail text before persistence.
- Add/extend tests for any security-relevant change.
- Run the full quality gates locally.

## Core-freeze gate
- If `requirements*.txt` or `pyproject.toml` changes, a staged ADR is mandatory.
- Enforced by pre-commit hook: `scripts/check_core_freeze.py`.

## Pull request requirements
- Fill the PR template and complete `docs/PR_REVIEW_CHECKLIST.md`.
- Include a short rollout and rollback note.
