Du arbeitest ausschließlich im Repo KUKANILEA.

MODUS
- Integrate

ZIEL
- Vereinheitliche nur Contract-Antworten (`summary`/`health`) ohne neue Features.

SCOPE
- Erlaubt: `app/contracts/*`, `app/modules/*/contracts.py`, `tests/contracts/*`
- Verboten: Router-Neubau, MIA-Neubau, UI-Refactor, CI-Refactor

MAIN-ONLY
- Arbeite auf `main`.
- Erstelle keine Branches.

ARBEITSWEISE
1) Finde genau eine Inkonsistenzgruppe.
2) Vereinheitliche minimal.
3) Ergänze/aktualisiere nur relevante Contract-Tests.

VALIDIERUNG
- `bash scripts/ops/healthcheck.sh --strict-doctor --skip-pytest`
- `pytest -q tests/contracts`

DOD
- Response-Form stabilisiert.
- Contract-Tests im Scope grün.
- Keine Änderungen außerhalb Scope.

AUSGABEFORMAT
1. Analyse
2. Änderung
3. Validierung
4. Restrisiken
5. Abschluss

