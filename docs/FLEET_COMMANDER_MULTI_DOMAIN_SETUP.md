# KUKANILEA Fleet Commander: Multi-Domain Setup

Zentrale Referenz fuer die 11 spezialisierten Worktrees inkl. Zuordnung zum aktuellen UI.

## Globale Guardrails (alle Agenten)
1. Domain Isolation: Nur im zugewiesenen Pfad arbeiten.
2. Offline-First: Keine externen Cloud-APIs fuer Produktlogik.
3. GoBD-Compliance: Revisionssichere Logs mit ISO-8601 UTC.
4. Performance: UI < 100ms, Server < 200ms (Zielwerte).

## Domain-Matrix (verknuepft)

| # | Domain | Worktree | Scope-Datei | Hauptpfade |
|---|---|---|---|---|
| 1 | Dashboard | `/Users/gensuminguyen/Kukanilea/worktrees/dashboard` | `docs/scopes/dashboard.md` | `app/templates/dashboard.html`, `app/core/observer.py`, `app/core/auto_evolution.py` |
| 2 | Upload & OCR | `/Users/gensuminguyen/Kukanilea/worktrees/upload` | `docs/scopes/upload.md` | `app/core/upload_pipeline.py`, `app/core/rag_sync.py`, `app/core/ocr_corrector.py` |
| 3 | Emailpostfach | `/Users/gensuminguyen/Kukanilea/worktrees/emailpostfach` | `docs/scopes/emailpostfach.md` | `app/mail/`, `app/plugins/mail.py`, `app/agents/mail.py` |
| 4 | Messenger | `/Users/gensuminguyen/Kukanilea/worktrees/messenger` | `docs/scopes/messenger.md` | `app/agents/orchestrator.py`, `app/agents/planner.py`, `app/agents/memory_store.py` |
| 5 | Kalender | `/Users/gensuminguyen/Kukanilea/worktrees/kalender` | `docs/scopes/kalender.md` | `app/knowledge/ics_source.py`, `app/knowledge/core.py` |
| 6 | Aufgaben | `/Users/gensuminguyen/Kukanilea/worktrees/aufgaben` | `docs/scopes/aufgaben.md` | `app/modules/projects/logic.py`, `app/modules/automation/` |
| 7 | Zeiterfassung | `/Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung` | `docs/scopes/zeiterfassung.md` | `app/web.py` (`/time`), `app/core/logic.py` |
| 8 | Projekte (Kanban) | `/Users/gensuminguyen/Kukanilea/worktrees/projekte` | `docs/scopes/projekte.md` | `app/modules/projects/`, `app/templates/kanban.html` |
| 9 | Excel/Docs Visualizer | `/Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer` | `docs/scopes/excel-docs-visualizer.md` | `app/templates/visualizer.html`, `app/core/logic.py` |
| 10 | Einstellungen | `/Users/gensuminguyen/Kukanilea/worktrees/einstellungen` | `docs/scopes/einstellungen.md` | `app/core/tenant_registry.py`, `app/core/mesh_network.py`, `app/routes/admin_tenants.py` |
| 11 | Floating Widget (AI Companion) | `/Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot` | `docs/scopes/floating-widget-chatbot.md` | `app/templates/layout.html` (global widget), Chat API in `app/web.py` |

## Aktuelles UI -> Domain-Mapping

| UI-Eintrag (Sidebar/Screen) | Route | Zugehoerige Domain |
|---|---|---|
| Dashboard | `/` | 1 Dashboard |
| Upload | `/` + `/upload` (POST) | 2 Upload & OCR |
| Aufgaben | `/projects` | 6 Aufgaben + 8 Projekte |
| Zeiterfassung | `/time` | 7 Zeiterfassung |
| CRM | `/crm/contacts` | 1 Dashboard (fachlich CRM-Surface, noch keine eigene Domain) |
| Dokumente | `/documents` | 9 Visualizer (Dokumenten-Surface) |
| Assistent | `/assistant` | 4 Messenger/Orchestrator |
| E-Mail | `/mail` | 3 Emailpostfach |
| Messenger | `/messenger` | 4 Messenger |
| Excel Visualizer | `/visualizer` | 9 Visualizer |
| Administration | Abschnitt | 10 Einstellungen |
| Mandanten | `/admin/tenants` | 10 Einstellungen |
| Forensic Monitor | `/admin/forensics` | 10 Einstellungen |
| Mesh-Netzwerk | `/admin/mesh` | 10 Einstellungen |
| Audit Trail | `/admin/audit` | 10 Einstellungen |
| Automatisierung | `/automation/rules` | 6 Aufgaben |
| Einstellungen | `/settings` | 10 Einstellungen |
| Floating Widget | global in `layout.html` | 11 Floating Widget |

## Master-Prompts (Kurzfassung)
- Dashboard: "Leitzentrale mit ObserverAgent und Queue-Status visualisieren."
- Upload: "OCR-Wisdom-Injection und Ingestion-Haertung."
- Emailpostfach: "Lokale Mail-Synchronisierung und KI-Entwuerfe."
- Messenger: "ReAct-Orchestrierung und Multi-Agenten-Kollaboration."
- Kalender: "Termin-Extraktion aus Dokumenten und lokale ICS-Logik."
- Aufgaben: "Background-Tasks/Automatisierung robust machen."
- Zeiterfassung: "Lueckenlose Erfassung + Exportpfad."
- Projekte: "Kanban mit Verlauf/Gedaechtnis."
- Visualizer: "Rendering und Dokumentenanalyse performant."
- Einstellungen: "Mandanten, Mesh, Lizenz, Governance."
- Floating Widget: "Kontextbewusster AI Companion in `layout.html`, Quick Actions, geringe Latenz."

## Wichtige Shared-Core-Warnung
Aenderungen an `app/web.py`, `app/core/logic.py`, `app/__init__.py`, `app/db.py` nur via `CROSS_DOMAIN_WARNING` und Konsolidierungs-Session.

## Overlap-Check (Pflicht vor Commit)
`python3 scripts/dev/check_domain_overlap.py --reiter <tab_slug> --files <changed_file_1> <changed_file_2> ...`
