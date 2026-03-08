# Session Tenant Enforcement Policy (AI Skill Runtime)

## Policy
- Tenant authority comes from authenticated server session context.
- Request payload values are treated as untrusted input.
- AI skill handlers must not trust caller-provided tenant identifiers.

## Runtime Rules
- `/api/ai/execute` returns `403 tenant_required` when session tenant is missing.
- `payload.tenant_id` is stripped before handler invocation.
- Handler receives canonical `tenant_id` from `current_tenant()`.

## Why
This prevents cross-tenant access attempts where an attacker injects a foreign tenant ID into AI skill payloads.
