# PR1 Spec: Re-Extract Path Resolution

## Goal
- Make re-extract resilient when a pending entry points to a stale `path`.
- Resolve the source file from DB (`versions.file_path`) if the file moved from intake to canonical storage.
- Keep behavior deterministic, allowlisted, and audited.

## In Scope
- Add shared resolver functions in both core variants:
  - `is_allowed_source_path(p: Path) -> bool`
  - `resolve_source_path(token: str, pending: dict | None = None, tenant_id: str = "") -> Path | None`
- Resolver order:
  1. Pending direct path (exists + allowlisted).
  2. Latest path from `db_latest_path_for_doc` (tenant-aware when available).
  3. Fallback SQL query on `versions` ordered by latest version.
  4. Return `None` if no allowlisted existing file is found.
- Update API/UI reextract endpoints to:
  - Use shared resolver.
  - Return deterministic `source_not_found` (HTTP 404) with meta:
    - `token`, `doc_id`, `tried_path`, `hint`
  - Audit:
    - success: `reextract_ok`
    - failure: `reextract_failed`

## Acceptance
- Re-extract succeeds when pending path is stale but latest `versions.file_path` exists under allowlisted roots.
- Re-extract fails with deterministic `source_not_found` and meta when no valid source is found.
- Resolver never returns paths outside allowlisted canonical roots.
- Success and failure are audit-logged.
- Tests cover moved-file fallback and allowlist enforcement.

## Out of Scope
- Metadata model expansion (Paperless-style entities).
- Job runner and automation orchestration.
- ML/LLM classification or safe-mode changes.
