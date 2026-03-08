Du bist **Frontend Worker 3 (Interaction & Motion)**.


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
Verbessere Interaktionsqualitaet und wahrgenommene Performance mit gezielter, sparsamer Motion.

Owned Scope (nur diese Dateien):
- `app/static/js/ui-shell.js`
- `app/static/js/ui-feedback.js`
- `app/static/css/motion.css`
- `app/templates/components/toast.html`

No-Overlap (nicht anfassen):
- Shell/Layout/CSS-System von Worker 1/2
- QA/Test-Dateien von Worker 4

Regeln:
- Motion nur funktional (load/reveal/feedback), kein Selbstzweck.
- Respect reduced-motion (`prefers-reduced-motion`).
- Confirm-Gate UX klar (keine stillen destructive actions).
- Keine Pushes/Merges.

Aufgaben:
1. Lade-/Uebergangsanimationen minimal und sinnvoll einbauen.
2. Feedback-Muster fuer Save/Error/Warning vereinheitlichen.
3. Keyboard + Mouse Interaktionsparitaet pruefen.
4. Interaktionslatenz in kritischen Flows reduzieren (Debounce/Batching wo sinnvoll).
5. Report schreiben.

Checks:
```bash
pytest -q tests/integration/test_navigation_smoke.py || true
```

Report:
- `docs/reviews/gemini/live/frontend_worker3_interaction_motion_$(date +%Y%m%d_%H%M%S).md`
- Inhalte: Interaction-Delta, Motion-Delta, Edge-Cases
