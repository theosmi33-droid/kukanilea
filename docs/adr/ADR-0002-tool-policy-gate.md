# ADR-0002: Tool execution + policy gate + allowlist

## Status
Accepted

## Context
Agents can propose actions. We must enforce deny-by-default RBAC and tool allowlists to prevent unintended execution.

## Decision
- Only the Orchestrator can execute tool actions.
- All tool actions are filtered by a policy gate (role + tenant + scope).
- Tool names are allowlisted explicitly in the Orchestrator.
- Any denied action creates an Audit event and a Task.

## Consequences
- Agents return intentions; they do not execute tools directly.
- Policy logic is centralized and testable.

## Alternatives Considered
- Allow agents to call tools directly (rejected: bypasses security boundary).
