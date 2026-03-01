# KUKANILEA Codex Project Assignments

Repo root: `/Users/gensuminguyen/Kukanilea/kukanilea_production`
Worktree root: `/Users/gensuminguyen/Kukanilea/worktrees`

## Shared blocked files for all projects
- `app/web.py`
- `app/core/logic.py`
- `app/__init__.py`
- `app/db.py`

## 1) dashboard
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/dashboard`
- Branch: `codex/dashboard`
- Allowlist:
  - `app/templates/dashboard.html`
  - `app/core/observer.py`
  - `app/core/auto_evolution.py`
  - `app/templates/components/system_status.html`
- Prompt:
  - You own tab `dashboard`. Work only in allowlist. If shared-core file is needed, stop and emit `CROSS_DOMAIN_WARNING`.

## 2) upload
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/upload`
- Branch: `codex/upload`
- Allowlist:
  - `app/core/upload_pipeline.py`
  - `app/core/ocr_corrector.py`
  - `app/core/rag_sync.py`
  - `app/templates/review.html`
  - `app/templates/dashboard.html` (upload widget only)
- Prompt:
  - You own tab `upload`. Harden ingestion/OCR/review flow only.

## 3) emailpostfach
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/emailpostfach`
- Branch: `codex/emailpostfach`
- Allowlist:
  - `app/mail/`
  - `app/agents/mail.py`
  - `app/plugins/mail.py`
  - `app/templates/messenger.html` (mail area)
- Prompt:
  - You own tab `emailpostfach`. Focus mailbox sync, threading, drafts, link-to-customer.

## 4) messenger
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/messenger`
- Branch: `codex/messenger`
- Allowlist:
  - `app/agents/orchestrator.py`
  - `app/agents/planner.py`
  - `app/agents/memory_store.py`
  - `app/templates/messenger.html`
- Prompt:
  - You own tab `messenger`. Optimize orchestrator/planner/reply loop.

## 5) kalender
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/kalender`
- Branch: `codex/kalender`
- Allowlist:
  - `app/knowledge/ics_source.py`
  - `app/knowledge/core.py`
  - `app/templates/generic_tool.html` (until dedicated template exists)
- MISSING_PATH:
  - dedicated route in `app/web.py`
  - dedicated calendar template
- Prompt:
  - You own tab `kalender`. Build local ICS ingestion and calendar UI surface; propose route/template patch via warning first.

## 6) aufgaben
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/aufgaben`
- Branch: `codex/aufgaben`
- Allowlist:
  - `app/modules/projects/logic.py`
  - `app/modules/automation/`
  - `app/templates/kanban.html`
- Prompt:
  - You own tab `aufgaben`. Task list/board movement and automation-triggered tasks.

## 7) zeiterfassung
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung`
- Branch: `codex/zeiterfassung`
- Allowlist:
  - `app/templates/generic_tool.html`
  - `app/modules/projects/logic.py` (project linkage only)
- Shared-core-needed:
  - `/time` and `/api/time/*` are implemented in `app/web.py` and `app/core/logic.py`
- Prompt:
  - You own tab `zeiterfassung`. If route/backend changes are needed in shared core, emit `CROSS_DOMAIN_WARNING` first.

## 8) projekte
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/projekte`
- Branch: `codex/projekte`
- Allowlist:
  - `app/modules/projects/`
  - `app/templates/kanban.html`
- Prompt:
  - You own tab `projekte` with MeisterTask-like board behavior.

## 9) excel_docs_visualizer
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer`
- Branch: `codex/excel-docs-visualizer`
- Allowlist:
  - `app/templates/visualizer.html`
  - `app/static/js/`
- Shared-core-needed:
  - `/visualizer` and data extraction currently in `app/web.py` + `app/core/logic.py`
- Prompt:
  - You own tab `excel_docs_visualizer`. UI/rendering first; request shared-core changes via warning.

## 10) einstellungen
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/einstellungen`
- Branch: `codex/einstellungen`
- Allowlist:
  - `app/core/tenant_registry.py`
  - `app/core/mesh_network.py`
  - `app/license.py`
  - `app/routes/admin_tenants.py`
  - `app/templates/settings.html`
- Prompt:
  - You own tab `einstellungen` (tenant/admin/mesh/license/branding).

## 11) floating-widget-chatbot
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot`
- Branch: `codex/floating-widget-chatbot`
- Allowlist:
  - `app/templates/layout.html`
  - `app/templates/partials/chat_widget.html`
  - `app/static/js/chat_widget.js`
  - `app/static/css/chat_widget.css`
- Shared-core-needed:
  - Chat API `/api/chat` currently implemented in `app/web.py`
- Prompt:
  - You own tab `floating_widget_chatbot`. Keep widget UX stable and light-mode-safe. If API contract changes are required, emit `CROSS_DOMAIN_WARNING` first.

## Standard assignment prompt template
Use this exact pattern:

- ROLE:
  - You are Lead Engineer for tab `<tab_slug>`.
- SCOPE:
  - Only edit files in allowlist for `<tab_slug>`.
- HARD STOP:
  - If a change touches blocked shared files, output `CROSS_DOMAIN_WARNING` and stop.
- PRE-COMMIT:
  - `python scripts/dev/check_domain_overlap.py --reiter <tab_slug> --files <changed_files>`
  - run tab-specific tests.

## Copy/Paste assignment prompts

### dashboard
```text
Du bist Lead Engineer fuer den Reiter "dashboard".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/dashboard
Branch: codex/dashboard
Du darfst nur diese Pfade aendern:
- app/templates/dashboard.html
- app/templates/components/system_status.html
- app/core/observer.py
- app/core/auto_evolution.py
Vor Commit MUSS laufen:
python scripts/dev/check_domain_overlap.py --reiter dashboard --files <changed_files>
Wenn shared-core betroffen ist, gib CROSS_DOMAIN_WARNING aus und stoppe.
```

### upload
```text
Du bist Lead Engineer fuer den Reiter "upload".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/upload
Branch: codex/upload
Erlaubte Pfade:
- app/core/upload_pipeline.py
- app/core/ocr_corrector.py
- app/core/rag_sync.py
- app/templates/review.html
- app/templates/dashboard.html (nur Upload-Bereich)
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter upload --files <changed_files>
```

### emailpostfach
```text
Du bist Lead Engineer fuer den Reiter "emailpostfach".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/emailpostfach
Branch: codex/emailpostfach
Erlaubte Pfade:
- app/mail/
- app/agents/mail.py
- app/plugins/mail.py
- app/templates/messenger.html (Mail-Bereich)
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter emailpostfach --files <changed_files>
```

### messenger
```text
Du bist Lead Engineer fuer den Reiter "messenger".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/messenger
Branch: codex/messenger
Erlaubte Pfade:
- app/agents/orchestrator.py
- app/agents/planner.py
- app/agents/memory_store.py
- app/templates/messenger.html
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter messenger --files <changed_files>
```

### kalender
```text
Du bist Lead Engineer fuer den Reiter "kalender".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/kalender
Branch: codex/kalender
Erlaubte Pfade:
- app/knowledge/ics_source.py
- app/knowledge/core.py
- app/templates/generic_tool.html
Hinweis: dedicated route/template ist MISSING_PATH. Falls noetig, nur via CROSS_DOMAIN_WARNING eskalieren.
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter kalender --files <changed_files>
```

### aufgaben
```text
Du bist Lead Engineer fuer den Reiter "aufgaben".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/aufgaben
Branch: codex/aufgaben
Erlaubte Pfade:
- app/modules/projects/logic.py
- app/modules/automation/
- app/templates/kanban.html
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter aufgaben --files <changed_files>
```

### zeiterfassung
```text
Du bist Lead Engineer fuer den Reiter "zeiterfassung".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung
Branch: codex/zeiterfassung
Erlaubte Pfade:
- app/templates/generic_tool.html
- app/modules/projects/logic.py (Projektverknuepfung)
Achtung: /time und /api/time/* liegen im shared core (app/web.py, app/core/logic.py).
Wenn erforderlich: CROSS_DOMAIN_WARNING und stoppen.
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter zeiterfassung --files <changed_files>
```

### projekte
```text
Du bist Lead Engineer fuer den Reiter "projekte".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/projekte
Branch: codex/projekte
Erlaubte Pfade:
- app/modules/projects/
- app/templates/kanban.html
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter projekte --files <changed_files>
```

### excel_docs_visualizer
```text
Du bist Lead Engineer fuer den Reiter "excel_docs_visualizer".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer
Branch: codex/excel-docs-visualizer
Erlaubte Pfade:
- app/templates/visualizer.html
- app/static/js/
Achtung: Datenzugriff liegt teilweise im shared core.
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter excel-docs-visualizer --files <changed_files>
```

### einstellungen
```text
Du bist Lead Engineer fuer den Reiter "einstellungen".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/einstellungen
Branch: codex/einstellungen
Erlaubte Pfade:
- app/core/tenant_registry.py
- app/core/mesh_network.py
- app/license.py
- app/routes/admin_tenants.py
- app/templates/settings.html
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter einstellungen --files <changed_files>
```

### floating-widget-chatbot
```text
Du bist Lead Engineer fuer den Reiter "floating_widget_chatbot".
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot
Branch: codex/floating-widget-chatbot
Erlaubte Pfade:
- app/templates/layout.html
- app/templates/partials/chat_widget.html
- app/static/js/chat_widget.js
- app/static/css/chat_widget.css
Achtung: Chat API liegt im shared core (`app/web.py`).
Wenn API/Backend-Aenderungen noetig sind: CROSS_DOMAIN_WARNING und stoppen.
Vor Commit:
python scripts/dev/check_domain_overlap.py --reiter floating-widget-chatbot --files <changed_files>
```
