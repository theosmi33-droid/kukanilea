# Release Conductor Preflight Behavior Note (2026-03-07)

## Ziel
Diese Notiz dokumentiert, warum `scripts/dev/release_conductor_preflight.sh` bewusst `bash -c` nutzt und wie Warning-/Fail-Zustände ausgewertet werden.

## Problembild
Bei `bash -lc` wurde in testnahen Umgebungen die `PATH`-Manipulation nicht konsistent übernommen.
Dadurch liefen Stubs für `gh` nicht zuverlässig an und die Tests für degrade/warn-verhalten konnten falsche Positivbefunde liefern.

## Korrektur
- `run_cmd()` nutzt jetzt `bash -c`.
- Ergebnis: gesetzte Umgebungsvariablen und PATH-Stubs bleiben stabil wirksam.

## Bewertungslogik (aktuell)
- `GUARD_RESULT=FAIL` -> Exit 1
- `TEST_RESULT=FAIL` -> Exit 1
- `GH_STATUS=warn` oder `RUN_STATUS=warn` oder `PROD_STATUS=warn` -> Exit 1

## Warum trotzdem sinnvoll
Die Preflight-Phase ist eine harte Release-Entscheidung. Warnungen für fehlende GH-CLI, fehlende Main-Run-Info oder fehlender Produktionspfad sollen den Lauf blockieren, damit kein „blinder“ Endflight startet.

## Testabdeckung
- `tests/test_release_conductor_preflight.py::test_preflight_handles_missing_gh_and_prod_path`
- `tests/test_release_conductor_preflight.py::test_preflight_prints_scope_summary`
- `tests/integration/test_mia_integration_readiness.py` (Readiness-Evidence, Dokumentationsanker)

## Offene Punkte
- Optionaler Modus `ALLOW_WARNINGS=1` könnte künftig eingeführt werden, wenn ein rein informativer Dry-Run benötigt wird.
- Aktuell ist der Modus bewusst fail-closed.
