# PR1C Spec: Re-Extract Cleanup and Resolver Consistency

## Scope
- Clean up PR1 resolver internals and remove duplicate lookup branches.
- Apply resolver to `/process/<token>` to prevent stale pending-path failures.
- Normalize upload API error envelope shape for deterministic responses.

## Changes
- `kukanilea_core.py` and `kukanilea_core_v3_fixed.py`
  - `db_latest_path_for_doc()` now delegates to a single internal DB lookup path.
  - DB ordering is consistent:
    - if `versions.version_no` exists: `ORDER BY version_no DESC, id DESC`
    - else: `ORDER BY id DESC`
  - `resolve_source_path()` now uses `db_latest_path_for_doc()` directly (no globals indirection).
  - Allowlist enforcement remains limited to `EINGANG`, `BASE_PATH`, `PENDING_DIR`, `DONE_DIR`.
- `kukanilea_api.py`
  - `/process/<token>` now resolves source through `resolve_source_path(...)`.
  - Returns deterministic `source_not_found` with meta when source cannot be resolved.
  - Adds audit entries for `process_ok` and `process_failed`.
- `kukanilea_upload.py`
  - Added minimal `_error_envelope(...)` with shape:
    - `{ ok: false, error: <code>, meta?: {...}, request_id?: <id> }`
  - Applied to `/api/reextract/<token>` and auth/not-found errors in upload API endpoints touched by PR1C.
  - `_is_allowed_path(...)` now reuses `core.is_allowed_source_path(...)` when available.

## Tests
- Extended `tests/test_reextract_path_resolution.py` with endpoint coverage:
  - `/process/<token>` succeeds when `pending.path` is stale but resolver finds the moved file path.

## Out of Scope
- New metadata entities (tags/correspondents/document types/storage paths/custom fields).
- Automation/job runner changes.
