# UX Top-20 Flows - KUKANILEA

This document tracks the critical UX flows and their implementation status for E2E testing.

## Implementation Status
- **Beta**: ≥80% Target (16/20)
- **RC**: ≥95% Target (19/20)
- **Prod**: 100% Target (20/20)

## Flow Definitions

| ID | Flow Name | Steps | Status | Gate Mapping |
|---|---|---|---|---|
| F01 | **Login** | Enter creds -> Dashboard | PASS | UX-G6 |
| F02 | **CRM Create** | Nav to CRM -> Add Contact -> Save | PASS | UX-G6 |
| F03 | **CRM Search** | Nav to CRM -> Type query -> Result | PASS | UX-G1 |
| F04 | **Tasks Move** | Nav to Tasks -> Drag/Button Move | PASS | UX-G1 |
| F05 | **Docs Upload** | Drag file -> Confirm -> Done | PASS | UX-G1 |
| F06 | **Error Handling** | Trigger 404/500 -> Back to Dashboard | PASS | UX-G3 |
| F07 | **Time Tracking** | Start timer -> Stop -> Book | TODO | |
| F08 | **Postfach Sync** | Nav to Mail -> Fetch -> List | TODO | |
| F09 | **Automation Create** | Builder -> Recipe -> Save | TODO | |
| F10 | **Lead Convert** | Open Lead -> Convert to Customer | TODO | |
| ... | ... | ... | ... | ... |

*Note: Initial Top-5 + Error Handling implemented for Beta.*
