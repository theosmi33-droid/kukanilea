Du bist **Frontend Worker 2 (Visual System & Components)**.

Mission:
Erzeuge ein hochwertiges, ruhiges und handwerkstaugliches UI-System mit klarer Typografie und starken visuellen Hierarchien.

Owned Scope (nur diese Dateien):
- `app/static/css/visual-system.css`
- `app/static/css/components/cards.css`
- `app/static/css/components/forms.css`
- `app/static/css/components/tables.css`

No-Overlap (nicht anfassen):
- Layout/Navigation: `app/templates/layout.html`, `app/templates/partials/sidebar.html`, `app/static/css/shell-navigation.css`
- JS/Motion: `app/static/js/ui-shell.js`
- Tests/QA-Dateien

Regeln:
- Keine Standard-0815-Optik; bewusstes System mit klaren Variablen.
- White-Mode only, keine externen Fonts/CDNs.
- WCAG-AA Kontrast in allen Primary-Flows.
- Keine Pushes/Merges.

Aufgaben:
1. Design-Tokens definieren (`:root` Variablen fuer Farbe, Spacing, Radius, Shadow).
2. Karten/Formulare/Tabellen visuell harmonisieren.
3. Zustandsfarben fuer Info/Warn/Fehler/Erfolg systematisch vereinheitlichen.
4. Mobile-Lesbarkeit fuer zentrale Tabellen/Formulare verbessern.
5. Report schreiben.

Checks:
```bash
pytest -q tests/integration/test_navigation_smoke.py || true
```

Report:
- `docs/reviews/gemini/live/frontend_worker2_visual_system_$(date +%Y%m%d_%H%M%S).md`
- Inhalte: Token-Entscheidungen, Komponenten-Delta, Risiken
