# Phase 2 QA Testcases

## Scope
This checklist covers manual validation before beta.

## Authentication and Session
- Login with valid credentials succeeds.
- Login with invalid credentials shows an error.
- Logout returns to login page.

## CRM
- `CRM -> Kunden` page renders without errors.
- Customer search works and updates table.
- Customer create works in normal mode and is blocked in read-only mode.

## Tasks/Kanban
- `Tasks` page renders with Todo/In Progress/Done columns.
- New task creation succeeds.
- Task move updates status and shows toast/flash.
- Task mutations are blocked in read-only mode.

## Documents / Knowledge
- `Knowledge -> Einstellungen` page renders.
- Source policy toggles are persisted.
- OCR policy remains fail-safe if binaries are missing.

## Workflows
- Workflow catalog loads and templates can be installed.
- Installed workflow can be enabled/disabled.
- Workflow details and logs render.

## AI Chat
- Chat widget opens from the floating button.
- AI status endpoint reports availability.
- AI chat request returns response payload and actions.
- AI feedback endpoint stores positive/negative feedback.
- If Ollama is unavailable, widget enters disabled state.

## Postfach / Mail
- Mail page renders with no server errors.
- Missing encryption key keeps mail actions fail-closed.

## Regression
- No PII in eventlog payload for AI/workflow events.
- Tenant isolation is preserved for list and search routes.
