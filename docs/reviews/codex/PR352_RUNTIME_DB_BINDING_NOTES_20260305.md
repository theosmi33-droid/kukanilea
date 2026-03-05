# PR352 Runtime Binding Notes (2026-03-05)

## Purpose

This note documents the expected runtime behavior behind PR #352 changes:

- explicit env path overrides must apply per Flask app instance
- tenant-scoped DB path overrides must rebind core logic on each request
- health endpoints remain reachable in minimal environments

## Runtime Contract

1. `KUKANILEA_AUTH_DB` maps to `app.config["AUTH_DB"]`.
2. `KUKANILEA_CORE_DB` maps to `app.config["CORE_DB"]`.
3. `KUKANILEA_LICENSE_PATH` maps to `app.config["LICENSE_PATH"]`.
4. `KUKANILEA_TRIAL_PATH` maps to `app.config["TRIAL_PATH"]`.
5. `_wire_runtime_env` updates both:
   - `DB_FILENAME`
   - `TOPHANDWERK_DB_FILENAME`
6. Before each request, tenant binding re-applies:
   - `app.core.logic.DB_PATH`
   - `app.core.logic._DB_INITIALIZED = False`

## Why This Matters

- Prevents stale global DB pointers after app reloads/tests.
- Avoids silent writes to the wrong tenant database.
- Keeps confirm-gate and audit effects tenant-correct under request switching.

## Evidence

The integration suite `tests/integration/test_runtime_db_binding.py` validates:

- env override mapping
- runtime env wiring
- per-request tenant DB binding
- DB rebind across consecutive requests
- health/ping route reachability with override paths

