Du arbeitest ausschließlich im Repo KUKANILEA.

MODUS
- Fix

ZIEL
- Repariere nur den kleinsten Blocker, der `healthcheck` oder `verify_guardrails` scheitern lässt.

SCOPE
- Erlaubt: `scripts/ops/*`, `tests/ops/*`, `app/contracts/*`, `tests/contracts/*`
- Verboten: UI-Templates, Frontend-Design, neue Module, CI-Refactor

MAIN-ONLY
- Arbeite auf `main`.
- Erstelle keine Branches.

ARBEITSWEISE
1) Root Cause identifizieren.
2) Kleinsten sicheren Patch umsetzen.
3) Re-Test nur im Scope.
4) Stop sobald DoD erreicht.

VALIDIERUNG
- `python scripts/ops/verify_guardrails.py`
- `bash scripts/ops/healthcheck.sh --strict-doctor --skip-pytest`
- relevante `pytest -q` im Scope

DOD
- Ein konkreter Root-Cause behoben.
- Relevante Checks für den Fix grün.
- Keine Scope-Expansion.

AUSGABEFORMAT
1. Analyse
2. Änderung
3. Validierung
4. Restrisiken
5. Abschluss

