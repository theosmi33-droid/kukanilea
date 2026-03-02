# KUKANILEA Fleet 11 Priority Command Center

## Ziel
Klare Priorisierung und eindeutiger Arbeitsfokus fuer die 11 Reiter, damit VS Code, Codex und Gemini CLI identisch arbeiten und keine Cross-Domain-Verwirrung entsteht.

## Single Source of Truth
- Manifest: `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/TAB_PATH_MANIFEST.md`
- Ownership: `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/TAB_OWNERSHIP_RULES.md`
- Assignments: `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/CODEX_PROJECT_ASSIGNMENTS.md`
- Overlap-Check: `/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py`
- Fleet helper: `/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/fleet_focus.py`
- Shared DB CLI: `/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py`
- Shared DB: `/Users/gensuminguyen/Kukanilea/data/agent_orchestra_shared.db`
- Fleet workspace: `/Users/gensuminguyen/Kukanilea/kukanilea_production/kukanilea_fleet.code-workspace`
- Team SOP: `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ANWEISUNG_KI_SYNC_FLEET11.md`

## Prioritaetsreihenfolge (11 Reiter)
1. Dashboard
2. Upload
3. Emailpostfach
4. Messenger
5. Kalender
6. Aufgaben
7. Zeiterfassung
8. Projekte
9. Visualizer
10. Einstellungen
11. Floating Widget Chatbot

## Arbeits-Lanes pro Reiter
- `Backend`: Business-Logik, APIs, Datenfluss, Tooling
- `Frontend`: Templates, JS, API-Bindings, Rendering
- `UI/UX`: Interaktionsfluss, Informationsdichte, visuelle Klarheit

## VS Code Bedienung (ohne Chaos)
1. `File -> Open Workspace from File...`
2. Waehle: `/Users/gensuminguyen/Kukanilea/kukanilea_production/kukanilea_fleet.code-workspace`
3. `Cmd+Shift+P -> Tasks: Run Task`
4. Nutze:
- `KUKANILEA: Fleet Board (11 Reiter)`
- `Fleet Focus: 01 Dashboard` ... `Fleet Focus: 11 Floating Widget Chatbot`

## Terminal Bedienung (Codex/Gemini CLI)
Fleet-Board anzeigen:
```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
python scripts/dev/fleet_focus.py --board
```

Expliziter Reiter-Fokus:
```bash
python scripts/dev/fleet_focus.py --focus dashboard
python scripts/dev/fleet_focus.py --focus upload
python scripts/dev/fleet_focus.py --focus floating-widget-chatbot
```

Codex-Prompt je Reiter erzeugen:
```bash
python scripts/dev/fleet_focus.py --focus dashboard --prompt codex
```

Gemini-CLI-Prompt je Reiter erzeugen:
```bash
python scripts/dev/fleet_focus.py --focus dashboard --prompt gemini
```

## Verbindlicher Shared-DB Ablauf (Pflicht)
1. `init + read`
2. `start-session`
3. `lock-domain`
4. Coden + `upsert-domain` + `heartbeat`
5. `unlock-domain` + `end-session`

Beispiel:
```bash
python scripts/shared_memory.py init
python scripts/shared_memory.py read
python scripts/shared_memory.py start-session --actor codex_dashboard --source codex --domain dashboard --branch codex/dashboard --worktree /Users/gensuminguyen/Kukanilea/worktrees/dashboard --note "start"
python scripts/shared_memory.py lock-domain --domain dashboard --session-id <SESSION_ID> --actor codex_dashboard --source codex --minutes 120 --reason "active_work"
```

## Pflichtregel vor jeder Datei-Aenderung
```bash
python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py \
  --reiter <reiter> --files <datei> --json
```

## Shared-Core Guardrail
Aenderungen an folgenden Dateien nur als zentraler Scope-Request:
- `app/web.py`
- `app/db.py`
- `app/core/logic.py`
- `app/__init__.py`

## GitHub Konfliktstrategie (praktisch)
1. Integrations-PR zuerst gruen bekommen und mergen.
2. Danach alle 11 Domain-Branches auf `main` rebasen.
3. Push immer mit `--force-with-lease`.
4. Je Domain nur ein fokussierter PR.

