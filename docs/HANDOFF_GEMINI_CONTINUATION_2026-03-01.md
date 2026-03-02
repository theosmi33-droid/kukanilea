# KUKANILEA Handover: Codex -> Gemini

## Meta
- Datum: 2026-03-01 (Europe/Berlin)
- Repository: `/Users/gensuminguyen/Kukanilea/kukanilea_production`
- Branch: `main`
- HEAD vor weiterem Commit: `b3f4555`
- Fokus heute: Sovereign-11 Shell-Stabilisierung (Sidebar-only + HTMX Navigation), Route-Stubs, Integration-Toolkit-Dateien.

## Was heute umgesetzt wurde (konkret)

### 1) Sovereign-11 Navigation/HTMX
Folgende Kernänderungen wurden implementiert:

- `/Users/gensuminguyen/Kukanilea/kukanilea_production/app/web.py`
  - HTMX-Helfer ergänzt:
    - `_is_hx_partial_request()`
    - `_render_sovereign_tool(tool_key, title, message, active_tab="dashboard")`
  - Canonical Routen ergänzt/vereinheitlicht:
    - `/dashboard`, `/upload`, `/tasks`, `/email`, `/calendar`
  - HTMX-Partial-Verhalten für bestehende Seiten ergänzt (Shell-in-Shell vermeiden):
    - `/mail`, `/settings`, `/projects`, `/messenger`, `/visualizer`, `/time`
  - Root-Anpassung:
    - `/` -> Redirect auf `/dashboard`

- `/Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/partials/sidebar.html`
  - Sidebar auf exakt 10 Reiter umgestellt:
    1. Dashboard `/dashboard`
    2. Upload `/upload`
    3. Projekte `/projects`
    4. Aufgaben `/tasks`
    5. Messenger `/messenger`
    6. Emailpostfach `/email`
    7. Kalender `/calendar`
    8. Zeiterfassung `/time`
    9. Visualizer `/visualizer`
    10. Einstellungen `/settings`
  - HTMX-Attribute auf Nav-Links gesetzt:
    - `hx-get`, `hx-target="#main-content"`, `hx-push-url="true"`, `hx-swap="innerHTML"`

- `/Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/layout.html`
  - Lokales HTMX eingebunden:
    - `/static/vendor/htmx.min.js`
  - Content-Target eingebaut:
    - `<div id="main-content" hx-history-elt>`
  - Sidebar-Active-State Script ergänzt (auch nach HTMX-Swaps)

- Neue Skeleton-Templates:
  - `/Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/skeletons/tool_partial.html`
  - `/Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/skeletons/tool_page.html`

### 2) Integration Toolkit / Scope Requests
Folgende Dateien wurden erstellt bzw. vorbereitet:

- `/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/integration/generate_scope_request.py`
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/templates/SCOPE_REQUEST_TEMPLATE.md`
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/scope_requests/core_sovereign-11-shell_20260301.md`
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/scope_requests/core_route-stubs_20260301.md`

## Browser-/Smoke-Status (Playwright)

Ergebnis der letzten UI-Tests:
- Alle 10 Hauptseiten antworten mit `200`:
  - `/dashboard`, `/upload`, `/projects`, `/tasks`, `/messenger`, `/email`, `/calendar`, `/time`, `/visualizer`, `/settings`
- Sidebar-Reihenfolge korrekt (10 Items).
- Sidebar-Klicks laden Inhalte ohne Full Reload (HTMX-Swap in `#main-content`).
- URL/History aktualisieren korrekt.

## Aktueller Arbeitsbaumstatus (wichtig)

Der Baum ist aktuell **dirty** mit mehreren bestehenden Änderungen, nicht nur aus dieser Session.

Kurzstatus laut `git status --short`:
- Modified:
  - `.env.example`
  - `.gitignore`
  - `MEMORY.md`
  - `app/agents/config/AGENTS.md`
  - `app/core/boot_sequence.py`
  - `app/core/logic.py`
  - `app/core/rag_sync.py`
  - `app/modules/automation/logic.py`
  - `app/templates/kanban.html`
  - `app/templates/layout.html`
  - `app/templates/partials/sidebar.html`
  - `app/web.py`
  - `docs/business/WELCOME_KIT.md`
  - `instance/hardware_profile.json`
- Untracked:
  - `app/static/js/command_palette.js`
  - `app/static/js/state.js`
  - `app/templates/skeletons/`
  - `docs/ENGINEERING_PROMPTS_DOMAINS_1_10.md`
  - `docs/MASTER_INSTRUCTIONS.md`
  - `docs/MASTER_INTEGRATION_PROMPT.md`
  - `docs/PRODUCT_DOMAINS_OVERVIEW.md`
  - `docs/scope_requests/`
  - `docs/templates/`
  - `scripts/integration/`

## Offene Punkte für Gemini (priorisiert)

1. Branch sauber aufsetzen (nicht auf `main` direkt weiterarbeiten):
   - Empfohlen: `codex/sovereign-11-core-integration`
2. Änderungen in logisch getrennte Commits teilen:
   - Commit A: Sovereign-11 Core UI (`app/web.py`, `layout.html`, `sidebar.html`, `skeletons/*`)
   - Commit B: Integration-Toolkit (`scripts/integration/*`, `docs/templates/*`, `docs/scope_requests/*`)
3. Regression-Check für bestehende Seiten durchführen:
   - Sicherstellen, dass Full-Page-Direct-Loads für `/projects`, `/time`, `/messenger`, `/visualizer`, `/settings`, `/email` weiter korrekt sind.
4. Optional/empfohlen:
   - `generate_scope_request.py` auf `git diff --binary` umstellen (für binäre Assets wie Fonts/Icons, falls später ergänzt).

## Konkrete Startkommandos für Gemini

```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production

# 1) Arbeitsbasis sichern
git status --short
git switch -c codex/sovereign-11-core-integration

# 2) App starten
python3 kukanilea_app.py --port 5051

# 3) Schneller Route-Check
for p in dashboard upload projects tasks messenger email calendar time visualizer settings; do
  curl -s -o /dev/null -w "%{http_code} %url_effective\n" "http://127.0.0.1:5051/$p";
done

# 4) Tests (mindestens Kernlauf)
pytest -q
```

## Copy/Paste Prompt für Gemini (Fortsetzung)

```text
Du arbeitest im Repo /Users/gensuminguyen/Kukanilea/kukanilea_production.

Lies zuerst diese Handover-Datei vollständig:
/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/HANDOFF_GEMINI_CONTINUATION_2026-03-01.md

Mission:
1) Übernimm den aktuellen Sovereign-11 Stand und validiere ihn erneut (Routes 200, HTMX no full reload, Sidebar exakt 10 Items).
2) Erstelle einen sauberen Branch codex/sovereign-11-core-integration.
3) Trenne in zwei Commits:
   - Core UI/Shell (web.py, layout, sidebar, skeletons)
   - Integration Toolkit/Scope-Requests (scripts+docs)
4) Keine destruktiven Git-Befehle. Keine Reverts von user-fremden Änderungen.
5) Erstelle einen präzisen Abschlussbericht mit:
   - tatsächlich geänderten Dateien
   - Testergebnissen
   - offenen Risiken
   - empfohlener PR-Reihenfolge

Guardrails:
- Domain-Isolation und Confirm-Gate Regeln respektieren.
- Offline-first beibehalten.
- Keine neuen Cloud-Abhängigkeiten.
```

## Hinweise zum Projekt 11 (Floating Widget)
- Vorgabe aus letzter Abstimmung war: „alles außer die 11 tools die laufen gerade“.
- Daher heute kein zusätzlicher Umbau im Widget-Modul vorgenommen.

## Day-End Checkliste (erledigt)
- [x] Kernänderungen dokumentiert
- [x] Fortsetzungs-Prompt für Gemini hinterlegt
- [x] Relevante Pfade/Kommandos hinterlegt
- [ ] Commit/Push bewusst offen gelassen (nach deiner finalen Freigabe)
