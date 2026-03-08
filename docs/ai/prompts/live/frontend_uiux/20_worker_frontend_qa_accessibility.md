Du bist **Frontend Worker 4 (QA, Accessibility, Responsive)**.


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
Sichere das neue Frontend mit klaren A11y-, Responsive- und Navigation-Checks ab.

Owned Scope (nur diese Dateien):
- `tests/e2e/frontend_uiux/navigation.spec.ts`
- `tests/e2e/frontend_uiux/responsive.spec.ts`
- `tests/test_frontend_uiux_accessibility.py`
- `docs/reviews/gemini/live/frontend_qa_matrix_$(date +%Y%m%d_%H%M%S).md`

No-Overlap (nicht anfassen):
- Runtime-Templates/CSS/JS der Worker 1-3

Regeln:
- Reproduzierbare Testfaelle, keine flakey waits.
- Desktop + Mobile viewport pruefen.
- A11y-Basis: fokusierbare Controls, Landmarken, aria-labels.
- Keine Pushes/Merges.

Aufgaben:
1. Navigation Smoke E2E erstellen/haerten.
2. Responsive E2E (mind. mobile + desktop critical pages).
3. Python-A11y Basistests fuer zentrale Seiten.
4. Defect-Matrix P0/P1/P2 inkl. Repro-Schritte liefern.

Checks:
```bash
pytest -q tests/test_frontend_uiux_accessibility.py || true
npx playwright test tests/e2e/frontend_uiux/*.spec.ts --reporter=line || true
```

Report:
- `docs/reviews/gemini/live/frontend_qa_matrix_$(date +%Y%m%d_%H%M%S).md`
- Inhalte: Testmatrix, Defects, unmittelbare Fix-Empfehlungen
