#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_ROOT = REPO_ROOT.parent
SHARED_DB = BASE_ROOT / 'data' / 'agent_orchestra_shared.db'
SHARED_CLI = REPO_ROOT / 'scripts' / 'shared_memory.py'

DOMAINS = [
    {
        'id': 'dashboard',
        'priority': 1,
        'label': 'Dashboard',
        'route': '/dashboard',
        'branch': 'codex/dashboard',
        'worktree': BASE_ROOT / 'worktrees' / 'dashboard',
        'lane': 'UI/UX + Frontend',
        'backend': ['app/core/observer.py', 'app/core/auto_evolution.py'],
        'frontend': ['app/templates/dashboard.html', 'app/templates/partials/sidebar.html'],
        'uiux': ['Widget-Dichte', 'Anomalie-Banner', 'Kompakte Executive-Ansicht'],
    },
    {
        'id': 'upload',
        'priority': 2,
        'label': 'Upload',
        'route': '/upload',
        'branch': 'codex/upload',
        'worktree': BASE_ROOT / 'worktrees' / 'upload',
        'lane': 'Backend + Frontend',
        'backend': ['app/core/upload_pipeline.py', 'app/core/ocr_corrector.py', 'app/core/rag_sync.py'],
        'frontend': ['app/templates/review.html', 'app/templates/dashboard.html'],
        'uiux': ['Drag&Drop', 'Progress', 'Review-Dialog mit Korrekturvorschlag'],
    },
    {
        'id': 'emailpostfach',
        'priority': 3,
        'label': 'Emailpostfach',
        'route': '/email',
        'branch': 'codex/emailpostfach',
        'worktree': BASE_ROOT / 'worktrees' / 'emailpostfach',
        'lane': 'Backend + Frontend',
        'backend': ['app/mail/', 'app/agents/mail.py', 'app/plugins/mail.py'],
        'frontend': ['app/templates/messenger.html'],
        'uiux': ['Inbox-Listenansicht', 'Draft-Flow', 'Attachment-Status'],
    },
    {
        'id': 'messenger',
        'priority': 4,
        'label': 'Messenger',
        'route': '/messenger',
        'branch': 'codex/messenger',
        'worktree': BASE_ROOT / 'worktrees' / 'messenger',
        'lane': 'Backend + UX',
        'backend': ['app/agents/orchestrator.py', 'app/agents/planner.py', 'app/agents/memory_store.py'],
        'frontend': ['app/templates/messenger.html'],
        'uiux': ['Chat-Flow', 'Agent-Tool-Actions', 'Antwort-Latenz'],
    },
    {
        'id': 'kalender',
        'priority': 5,
        'label': 'Kalender',
        'route': '/calendar',
        'branch': 'codex/kalender',
        'worktree': BASE_ROOT / 'worktrees' / 'kalender',
        'lane': 'Backend + Frontend',
        'backend': ['app/knowledge/ics_source.py', 'app/knowledge/core.py'],
        'frontend': ['app/templates/generic_tool.html'],
        'uiux': ['Woche/Monat', 'Frist-Highlights', 'ICS-Export-Klarheit'],
    },
    {
        'id': 'aufgaben',
        'priority': 6,
        'label': 'Aufgaben',
        'route': '/tasks',
        'branch': 'codex/aufgaben',
        'worktree': BASE_ROOT / 'worktrees' / 'aufgaben',
        'lane': 'Backend + Frontend',
        'backend': ['app/modules/automation/', 'app/modules/projects/logic.py'],
        'frontend': ['app/templates/kanban.html'],
        'uiux': ['Assign/Accept/Reject', 'Status-Flow', 'Dead-Letter-Transparenz'],
    },
    {
        'id': 'zeiterfassung',
        'priority': 7,
        'label': 'Zeiterfassung',
        'route': '/time',
        'branch': 'codex/zeiterfassung',
        'worktree': BASE_ROOT / 'worktrees' / 'zeiterfassung',
        'lane': 'Backend + Reporting UX',
        'backend': ['app/web.py (time route)', 'app/core/logic.py (time tables)'],
        'frontend': ['app/templates/generic_tool.html'],
        'uiux': ['Stoppuhr', 'Admin-Übersicht', 'CSV-Export'],
    },
    {
        'id': 'projekte',
        'priority': 8,
        'label': 'Projekte',
        'route': '/projects',
        'branch': 'codex/projekte',
        'worktree': BASE_ROOT / 'worktrees' / 'projekte',
        'lane': 'Frontend + Backend',
        'backend': ['app/modules/projects/'],
        'frontend': ['app/templates/kanban.html'],
        'uiux': ['Kanban Drag&Drop', 'Kommentare', 'Aktivitäts-Log'],
    },
    {
        'id': 'excel-docs-visualizer',
        'priority': 9,
        'label': 'Visualizer',
        'route': '/visualizer',
        'branch': 'codex/excel-docs-visualizer',
        'worktree': BASE_ROOT / 'worktrees' / 'excel-docs-visualizer',
        'lane': 'Frontend + Rendering',
        'backend': ['app/core/logic.py (document read/index)'],
        'frontend': ['app/templates/visualizer.html', 'app/static/js/'],
        'uiux': ['Lesbarkeit großer Docs', 'Excel-Tabellenfluss', 'Zusammenfassung'],
    },
    {
        'id': 'einstellungen',
        'priority': 10,
        'label': 'Einstellungen',
        'route': '/settings',
        'branch': 'codex/einstellungen',
        'worktree': BASE_ROOT / 'worktrees' / 'einstellungen',
        'lane': 'Backend + Governance UX',
        'backend': ['app/core/tenant_registry.py', 'app/core/mesh_network.py', 'app/license.py'],
        'frontend': ['app/templates/settings.html', 'app/templates/admin_tenants.html'],
        'uiux': ['Admin-Unterreiter', 'Sicherheits-Confirm-Gates', 'Backup-Transparenz'],
    },
    {
        'id': 'floating-widget-chatbot',
        'priority': 11,
        'label': 'Floating Widget Chatbot',
        'route': 'overlay',
        'branch': 'codex/floating-widget-chatbot',
        'worktree': BASE_ROOT / 'worktrees' / 'floating-widget-chatbot',
        'lane': 'UI/UX + Agent Integration',
        'backend': ['app/web.py (/api/chat*)'],
        'frontend': ['app/templates/layout.html', 'app/templates/partials/chat_widget.html', 'app/static/js/chat_widget.js'],
        'uiux': ['Global erreichbar', 'Kontext-aware Aktionen', 'Minimiert weiter aktiv'],
    },
]

DOMAIN_BY_ID = {d['id']: d for d in DOMAINS}


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False).returncode


def _table() -> str:
    lines = []
    header = f"{'Prio':<4}  {'Reiter':<26}  {'Route':<12}  {'Lane':<24}  {'Branch':<35}"
    lines.append(header)
    lines.append('-' * len(header))
    for d in DOMAINS:
        lines.append(
            f"{d['priority']:<4}  {d['label']:<26}  {d['route']:<12}  {d['lane']:<24}  {d['branch']:<35}"
        )
    return '\n'.join(lines)


def _focus(domain_id: str) -> str:
    d = DOMAIN_BY_ID[domain_id]
    sid = f"$SOURCE:$ACTOR:{d['id']}:$RAND"
    lines = [
        f"Reiter: {d['label']} (prio {d['priority']})",
        f"Route: {d['route']}",
        f"Branch: {d['branch']}",
        f"Worktree: {d['worktree']}",
        f"Lane: {d['lane']}",
        '',
        'Backend scope:',
        *[f'  - {x}' for x in d['backend']],
        'Frontend scope:',
        *[f'  - {x}' for x in d['frontend']],
        'UI/UX scope:',
        *[f'  - {x}' for x in d['uiux']],
        '',
        'Startkommandos:',
        f'  cd {d["worktree"]}',
        f'  python {SHARED_CLI} init',
        f'  python {SHARED_CLI} read',
        (
            '  python '
            f'{SHARED_CLI} start-session --actor <actor> --source <codex|gemini|vscode> '
            f'--domain {d["id"]} --branch {d["branch"]} --worktree {d["worktree"]} --note "start"'
        ),
        (
            '  python '
            f'{SHARED_CLI} lock-domain --domain {d["id"]} --session-id <session_id> '
            '--actor <actor> --source <codex|gemini|vscode> --minutes 120 --reason "active_work"'
        ),
        (
            '  python '
            '/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py '
            f'--reiter {d["id"]} --files <deine_datei> --json'
        ),
        (
            '  python '
            f'{SHARED_CLI} upsert-domain --domain {d["id"]} --action "<action>" '
            '--commit <hash_or_local_only> --status IN_PROGRESS --actor <actor> --source <codex|gemini|vscode>'
        ),
        f'  # DB: {SHARED_DB}',
    ]
    return '\n'.join(lines)


def _prompt(domain_id: str, agent: str) -> str:
    d = DOMAIN_BY_ID[domain_id]
    shared = (
        'Domain Isolation strikt einhalten. Keine Änderungen an app/web.py, app/db.py, app/core/logic.py '
        'ohne CROSS_DOMAIN_WARNING. Offline-first, GoBD-Logs, Confirm-Gate für destructive actions.'
    )
    sync = (
        f'Starte immer mit `python {SHARED_CLI} init && python {SHARED_CLI} read`, '
        f'dann `start-session` + `lock-domain` für `{d["id"]}`. '
        'Nach jedem Schritt `upsert-domain`, alle 10-15 Min `heartbeat`, am Ende `unlock-domain` + `end-session`.'
    )
    if agent == 'codex':
        return (
            f"Du bist Lead für Reiter '{d['label']}'. Arbeitsbereich: {d['worktree']}. "
            f"Branch: {d['branch']}. Fokus-Lane: {d['lane']}. {shared} {sync} "
            f"Liefere zuerst: 1) Delta-Analyse, 2) minimalen Patch, 3) Testnachweis. Route-Kontext: {d['route']}."
        )
    return (
        f"ROLE: Principal Engineer for '{d['label']}'. PATH: {d['worktree']}. BRANCH: {d['branch']}. "
        f"OBJECTIVE: Work only inside this domain and ship stable increments for route {d['route']}. "
        f"RULES: {shared} {sync} Execute in loop: Analyze -> Implement -> Test -> Report."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='KUKANILEA 11-domain focus helper')
    parser.add_argument('--board', action='store_true', help='Show priority board')
    parser.add_argument('--focus', choices=sorted(DOMAIN_BY_ID.keys()), help='Show details for one domain')
    parser.add_argument('--open', action='store_true', help='Open domain worktree in VS Code (new window)')
    parser.add_argument('--prompt', choices=['codex', 'gemini'], help='Print kickoff prompt for focused domain')
    parser.add_argument('--json', action='store_true', help='Emit JSON')
    args = parser.parse_args()

    if args.board:
        if args.json:
            print(json.dumps(DOMAINS, indent=2, ensure_ascii=False))
        else:
            print(_table())
        return 0

    if args.focus:
        if args.open:
            _run(['code', '-n', str(DOMAIN_BY_ID[args.focus]['worktree'])], cwd=REPO_ROOT)
        if args.prompt:
            print(_prompt(args.focus, args.prompt))
        elif args.json:
            print(json.dumps(DOMAIN_BY_ID[args.focus], indent=2, ensure_ascii=False))
        else:
            print(_focus(args.focus))
        return 0

    parser.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
