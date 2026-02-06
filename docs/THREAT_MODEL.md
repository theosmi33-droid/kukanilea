# Threat Model

## Assets
- Tenant-scoped documents and extracted text
- Audit logs and task records
- Authentication credentials

## Threats
- **Prompt injection**: malicious instructions in user input or documents.
- **Data exfiltration**: attempts to dump DB or system prompts.
- **Tenant escape**: cross-tenant data access or filesystem traversal.
- **Tool abuse**: executing destructive actions without policy gates.

## Mitigations
- Treat all content as untrusted; sanitize before LLM usage.
- Deny-by-default policy gates and tool allowlists.
- Tenant scoping on every query and filesystem access.
- Audit + task creation on blocked or denied actions.

## Residual Risks
- False positives from heuristic filters.
- Local filesystem permissions outside the app boundary.
