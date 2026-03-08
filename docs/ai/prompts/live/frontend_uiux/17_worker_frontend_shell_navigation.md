Du bist **Frontend Worker 1 (Shell & Navigation)**.

## Repo-Modus fuer Codex Cloud (verbindlich)

Fuehre zuerst aus:
1. `git status --short`
2. `git branch --all`
3. `git remote -v`

Danach entscheide automatisch:
- **Fall A (`main` + `origin` + Fetch verfuegbar):**
  - `git fetch origin --prune`
  - `git checkout main`
  - `git pull --ff-only origin main`
- **Fall B (Remote/Fetch fehlt oder blockiert, Working Tree aber sauber):**
  - aktuellen Checkout als autorisierten Cloud-Snapshot nutzen
  - keinen neuen Branch anlegen, keinen erneuten Remote-Fetch versuchen
  - mit der Frontend-Aufgabe normal fortfahren
- **Fall C (Working Tree unerwartet dirty/inkonsistent):**
  - sofort stoppen, keinen Produktcode aendern
  - nur Blocker + kleinste manuelle Next Action melden

Mission:
Baue eine klare, schnelle und angenehm nutzbare Frontend-Shell fuer KUKANILEA.

Owned Scope (nur diese Dateien):
- `app/templates/layout.html`
- `app/templates/partials/sidebar.html`
- `app/templates/partials/topbar.html`
- `app/static/css/shell-navigation.css`

No-Overlap (nicht anfassen):
- Design-Tokens/Systemstil: `app/static/css/visual-system.css`
- Motion/JS: `app/static/js/ui-shell.js`
- Tests/QA: `tests/e2e/frontend_uiux/*.spec.ts`, `tests/test_frontend_uiux_accessibility.py`

Regeln:
- White-Mode only, Zero-CDN, lokale Assets.
- HTMX/Navigation konsistent (kein Mischchaos aus Redirect/Partial ohne Konzept).
- Focus-Ringe und Keyboard-Navigation muessen sichtbar und nutzbar sein.
- Keine Pushes/Merges.

Aufgaben:
1. Sidebar-Informationsarchitektur vereinfachen (Prioritaeten vor Vollstaendigkeit).
2. Header + Seitenrahmen klar strukturieren (Desktop + Mobile).
3. Aktive Navigation robust markieren (Pfad/Route-basiert).
4. Skip-Link + Landmarken (`main`, `nav`, `header`) sauber implementieren.
5. Report schreiben.

Checks:
```bash
pytest -q tests/integration/test_navigation_smoke.py || true
pytest -q tests/test_sidebar_ux.py || true
```

Report:
- `docs/reviews/gemini/live/frontend_worker1_shell_nav_$(date +%Y%m%d_%H%M%S).md`
- Inhalte: Current State, Changes, P0/P1/P2, offene Blocker
