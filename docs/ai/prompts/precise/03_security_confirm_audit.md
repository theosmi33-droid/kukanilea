Du arbeitest ausschließlich im Repo KUKANILEA.

MODUS
- Harden

ZIEL
- Härte Confirm-/Audit-/Guardrail-Pfade gegen unkontrollierte Write-Aktionen.

SCOPE
- Erlaubt: `kukanilea/orchestrator/*`, `kukanilea/guards.py`, `tests/*guard*`, `tests/*orchestrator*`, `tests/*security*`
- Verboten: neue Features außerhalb Security-Pfad, UI-Redesign

MAIN-ONLY
- Arbeite auf `main`.
- Erstelle keine Branches.

ARBEITSWEISE
1) Einen echten weichen Punkt identifizieren.
2) Kleinsten fail-closed Patch setzen.
3) Nur betroffene Security-Tests ausführen.

VALIDIERUNG
- `python scripts/ops/verify_guardrails.py`
- relevante `pytest -q -k "guardrail or confirm or audit or router"`

DOD
- Kein Write ohne Confirm.
- Audit-Ereignis auf kritischem Pfad sichtbar.
- Injection führt zu safe fallback/block.

AUSGABEFORMAT
1. Analyse
2. Änderung
3. Validierung
4. Restrisiken
5. Abschluss

