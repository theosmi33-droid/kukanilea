# Tool Actions Tenant Binding Policy

## Scope
- Endpoint family: `/api/<tool>/actions/<name>`
- Runtime: `app/modules/actions_api.py`

## Security Contract
- Client payload is untrusted for tenant context.
- Server session (`current_tenant()`) is the single source of tenant authority.
- Incoming tenant hints are removed before handler dispatch:
  - `tenant_id`
  - `tenant`
  - `tenantId`
- Canonical `tenant_id` is injected into handler payload.

## Required Tests
- A regression test must prove payload spoofing is ignored for at least one read-path action.
- A regression test must prove payload spoofing is ignored for at least one mail action path.

## Rationale
Without central tenant binding, handlers that trust payload tenant hints can read or mutate data across tenant boundaries.
