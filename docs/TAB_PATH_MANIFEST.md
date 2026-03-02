# KUKANILEA Tab Path Manifest

Repo root: `/Users/gensuminguyen/Kukanilea/kukanilea_production`
Generated: 2026-03-01

This manifest is the source of truth for per-tab ownership.
If a required route/template is missing, it is marked as `MISSING_PATH`.

## Shared Critical Files
- `app/web.py`
- `app/core/logic.py`
- `app/__init__.py`
- `app/db.py`

## Tabs

| Tab | UI route(s) | Primary logic path(s) | UI template path(s) | Status |
|---|---|---|---|---|
| dashboard | `/` | `app/core/auto_evolution.py`, `app/core/observer.py` | `app/templates/dashboard.html` | READY |
| upload | `/upload` (POST), `/review/<token>/kdnr` | `app/core/upload_pipeline.py`, `app/core/rag_sync.py`, `app/core/ocr_corrector.py` | `app/templates/dashboard.html`, `app/templates/review.html` | READY (no dedicated upload page) |
| emailpostfach | `/mail`, `/api/mail/draft`, `/api/mail/eml` | `app/mail/`, `app/agents/mail.py`, `app/plugins/mail.py` | `app/templates/messenger.html` | READY |
| messenger | `/messenger`, `/api/chat` | `app/agents/orchestrator.py`, `app/agents/planner.py`, `app/agents/memory_store.py` | `app/templates/messenger.html` | READY |
| kalender | `MISSING_PATH` (no dedicated calendar route in web.py) | `app/knowledge/ics_source.py`, `app/knowledge/core.py` | `MISSING_PATH` (no calendar template) | PARTIAL |
| aufgaben | `/projects`, `/api/tasks`, `/api/tasks/<task_id>/move` | `app/modules/projects/logic.py`, `app/modules/automation/`, `app/core/` | `app/templates/kanban.html` | READY |
| zeiterfassung | `/time`, `/api/time/*` | `app/web.py` (time section), `app/core/logic.py` (time tables/ops) | `app/templates/generic_tool.html` | READY (shared-core heavy) |
| projekte | `/projects` | `app/modules/projects/` | `app/templates/kanban.html` | READY |
| excel_docs_visualizer | `/visualizer`, `/documents` | `app/core/logic.py` (read/index), `app/web.py` visualizer/docs handlers | `app/templates/visualizer.html` | READY (shared-core heavy) |
| einstellungen | `/settings`, `/settings/branding`, `/admin/tenants`, `/admin/mesh`, `/admin/audit` | `app/core/tenant_registry.py`, `app/core/mesh_network.py`, `app/license.py`, `app/routes/admin_tenants.py` | `app/templates/settings.html`, `app/templates/admin_tenants.html`, `app/templates/audit_trail.html` | READY |
| floating_widget_chatbot | global floating widget, `/api/chat` | `app/templates/layout.html` (inline widget + script), `app/web.py` (`/api/chat`) | `app/templates/layout.html` | PARTIAL (dedicated partial/js/css pending) |

## Notes
- Sidebar currently shows: Dashboard, Upload, Aufgaben, Zeiterfassung, CRM, Dokumente, Assistent, E-Mail, Messenger, Excel Visualizer, Einstellungen.
- Floating widget chatbot ist aktuell inline in `app/templates/layout.html` implementiert und nutzt `/api/chat` aus `app/web.py`; dedizierte Dateien fuer Partial/JS/CSS sind als eigener Ausbauschritt vorgesehen.
- Requested tab `kalender` is not yet represented as dedicated route/template and must be built as a new domain feature.
