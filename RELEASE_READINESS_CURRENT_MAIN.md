# Release-Readiness Report (current main baseline)

Stand: 2026-03-12 (UTC)

## Grün
- Guardrail-Check erfolgreich (`python scripts/ops/verify_guardrails.py`): CDN/External-Assets/HTMX-Checks ohne Befund.
- Relevante Sovereign-/Asset-Tests grün (`pytest -q tests/test_sovereign11_gate.py tests/test_static_assets_single_source_guard.py`): 5/5 Tests bestanden.

## Blockiert
- Voller Healthcheck (`bash scripts/ops/healthcheck.sh`) lief innerhalb des gesetzten Laufzeitfensters nicht bis zum Abschluss (`timeout 180 ...` -> Exit 124), daher kein vollständiger End-to-End-Gesamtstatus.

## Akzeptiertes Restrisiko
- Ohne vollständigen Healthcheck-Abschluss bleibt ein Restrisiko für ungetestete Integrationspfade bestehen.

## Drei zwingende nächste Schritte
1. `origin/main` synchronisieren (`git fetch origin --prune && git checkout main && git pull --ff-only`).
2. `bash scripts/ops/healthcheck.sh` ohne Timeout vollständig bis Exit 0 durchlaufen lassen und Ergebnis protokollieren.
3. Bei erneutem Healthcheck-Laufzeitproblem: langsame/klemmende Testphase identifizieren (pytest-Selektion + Dauerprofil), Engpass beheben und Healthcheck erneut grün ziehen.
