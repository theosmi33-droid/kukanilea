# Security Model: Prompt Injection Defense

## Principles
- **Untrusted by default**: All external content (emails, PDFs, chats, WhatsApp) is untrusted.
- **Policy isolation**: Untrusted content cannot alter roles, tenant scope, tools, or system policy.
- **Deterministic decisions**: Routing and access checks are deterministic and enforced server-side.

## Controls
- **Tenant isolation**: Every query/action is filtered by tenant_id.
- **RBAC deny-by-default**: Roles gate tools and data exposure.
- **Safe tool validation**: Tool arguments are validated (paths limited to tenant base).
- **No tool escalation**: User content cannot request privileged tools not allowed by role.

## Implementation Guidance
- Treat extracted text as data, never as instructions.
- Never concatenate untrusted text into prompts used for policy or tool selection.
- Reject tool calls with path traversal or cross-tenant access.

## Audit
- All tool calls write audit events (action + tenant_id + user + metadata).
