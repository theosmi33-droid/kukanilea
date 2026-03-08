# PR 627 Security Review (Visualizer Tenant Isolation)

## Risk Addressed
- Cross-tenant document access through visualizer source-path APIs.

## Fix Summary
- Enforce tenant-root path validation for render and summary endpoints.
- Reject cross-tenant file paths with `403 forbidden_tenant_path`.
- Preserve existing allowed-path and file-existence checks.

## Evidence
- `tests/test_visualizer_api.py::test_render_endpoint_blocks_cross_tenant_path`
- `tests/test_visualizer_api.py::test_summary_endpoint_blocks_cross_tenant_path`
- `tests/security/test_visualizer_tenant_path_guard.py`
- `tests/integration/test_visualizer_tenant_error_contract.py`
