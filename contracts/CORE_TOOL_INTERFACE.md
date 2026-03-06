# KUKANILEA CORE TOOL INTERFACE CONTRACT (MIA-C1)

Version: 2026-03-06
Status: MANDATORY

## 1. Action Naming Convention
All actions exposed to the MIA-Orchestrator must follow:
`<domain>.<entity>.<verb>`

Examples:
- `time.entry.start`
- `docs.file.delete`
- `mail.message.send`

## 2. Risk & Confirm-Gate Policy

| Risk Level | Category | Requirements | User Interaction |
| :--- | :--- | :--- | :--- |
| **L0** | Read/Discovery | None | Immediate |
| **L1** | Safe Mutation | Audit Log | Visual Feedback |
| **L2** | Destructive/External | Audit Log + Confirm-Gate | **Explicit Confirm Required** |

### L2 Action Allowlist (Requires `Confirm-Gate`)
- `docs.file.delete`
- `mail.message.send`
- `auth.user.disable`
- `time.entry.approve` (if Manager-role)

## 3. Tool Response Schema (MIA-Envelope)
Every tool execution MUST return:

```json
{
  "action": "domain.entity.verb",
  "status": "ok | error | deferred",
  "payload": { ... },
  "audit": {
    "event_type": "action.domain.verb.status",
    "risk_level": "L0|L1|L2"
  },
  "confirm_required": true/false
}
```

## 4. Domain Isolation
- Codex Workers MUST NOT modify `app/agents/orchestrator.py`.
- Shared logic (Confirm-Gates, Audit) resides in `app/security/` and `app/core/audit.py`.
- Domain-specific logic resides in `app/modules/<domain>/`.

## 5. Offline-First Compliance
- No tool may rely on external APIs (Tavily, SendGrid) without a deterministic `local_fallback` state.
- Fallback for `mail.message.send` is `mail.draft.save_local`.
