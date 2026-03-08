# PR 624 Security Review (Session Tenant Enforcement)

## Scope
- API endpoint: `/api/ai/execute`
- Skills in scope: `email.search`, `email.draft_reply`, `email.send_reply`

## Risk Addressed
- Cross-tenant parameter injection via `payload.tenant_id` in AI skill execution.

## Expected Behavior
- The effective tenant is always derived from authenticated session context.
- Missing session tenant fails closed with `403 tenant_required`.
- Untrusted `payload.tenant_id` is ignored and never reaches skill handlers as authority.

## Evidence
- Integration test for payload override guard:
  - `tests/integration/test_emailpostfach_ai_actions.py::test_email_execute_enforces_session_tenant`
- Integration test for send path:
  - `tests/integration/test_emailpostfach_ai_tenant_payload_stripping.py::test_ai_execute_overrides_payload_tenant_for_send_reply`
- Security test for fail-closed behavior:
  - `tests/security/test_email_skill_session_tenant_guard.py::test_ai_execute_rejects_missing_session_tenant`
