# Roadmap

## Phase 3 Enterprise Sanierung (KUKANILEA Transformation)
- **Architektur:** Flask-Blueprints durchgesetzt, Legacy-Files gelöscht, OpenClaw (3 Orchestrators, 15 Workers) vorbereitet.
- **Blueprints:** `SOUL.md`, `AGENTS.md`, `TOOLS.md` unter `app/agents/config/` erstellt für strikte KI-Verhaltensregeln.
- **UI/UX:** Radikaler Font-Reset auf System-Stack, Windows-Boot-Login-Simulation integriert, Glassmorphism & Haptic-Feedback via Tailwind-Tokens.
- **Performance:** SQLite WAL-Modus und `synchronous = NORMAL` verifiziert.
- **Sicherheit:** ClamAV (pyclamd) Scanner-Block beim Upload eingebaut, Prompt Injection Defense Delimiter (`### USER INPUT ###`) in LLM Prompts eingefügt.
- **Verification:** Playwright E2E KPI-Benchmark Script in `scripts/tests` implementiert.

## Phase 2 Product Core (Handwerk)
- Work time tracking (projects, timers, approvals, CSV export).
- Jobs/projects/tasks core with deterministic reminders.
- Document intake → review → archive hardening.

## v1 Local Agent Orchestra
- App factory + blueprint structure.
- Deterministic agent orchestration (no LLM runtime).
- Tenant-safe auth and storage boundaries.
- Upload → Extract → Review → Archive flow.

## v2 Multi-Tenant Hosted
- Hosted auth provider + stronger RBAC.
- Tenant isolation at DB + storage layers.
- Audit log UI and export.

## v3 LLM Drop-in
- LLMProvider interface implementation.
- Optional provider selection (on-prem/cloud).
- Summarization + intent parsing extensions.
