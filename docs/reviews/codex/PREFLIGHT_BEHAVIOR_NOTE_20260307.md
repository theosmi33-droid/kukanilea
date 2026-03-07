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

## Operative Entscheidungs-Matrix
| Bedingung | Erwartetes Verhalten | Exit-Code |
|---|---|---|
| `pr_quality_guard=PASS`, `tests=PASS`, `gh/runs/prod=ok` | Freigabe möglich | `0` |
| `pr_quality_guard=FAIL` | Harter Block, keine Freigabe | `1` |
| `tests=FAIL` | Harter Block, keine Freigabe | `1` |
| `gh=warn` | Block wegen fehlender Merge-Transparenz | `1` |
| `runs=warn` | Block wegen fehlender CI-Transparenz | `1` |
| `prod=warn` | Block wegen fehlender Produktions-Evidenz | `1` |

## Warum `gh/runs/prod` warnend-blockierend sind
1. Ohne `gh pr list` fehlt die Sicht auf konkurrierende Änderungen.
2. Ohne `gh run list` fehlt die Sicht auf den letzten Main-Gesundheitszustand.
3. Ohne Produktions-Clone-Status fehlt der Abgleich gegen die lokale Realumgebung.
4. Die Kombination dieser drei Unsicherheiten erzeugt ein hohes Risiko für unbemerkte Regressionen.

## Runbook: Fehlerbehebung
1. `gh`-Warnung
   `gh auth status` prüfen, Token-Scope `repo, workflow` sicherstellen.
2. `runs`-Warnung
   API-Ratelimit und Org-Berechtigungen prüfen, ggf. `gh run list --limit 5` separat ausführen.
3. `prod`-Warnung
   `PROD_REPO_PATH` korrigieren und `git -C \"$PROD_REPO_PATH\" status --short` verifizieren.
4. Nach Korrektur Preflight erneut starten und Ergebnis artefaktieren.

## CI/Local-Konsistenz
- Lokal und CI müssen denselben Exit-Code aus denselben Inputs liefern.
- Die Tests prüfen explizit den Warning-/Fail-Pfad, damit keine stille Semantikdrift entsteht.
- Das reduziert „works on my machine“-Effekte im Merge-Endflight.

## Folgeaufgabe (nicht in diesem PR)
- Optional kann ein `--strict` / `--advisory` Modus ergänzt werden:
  - `strict` (Default): aktuelles fail-closed Verhalten.
  - `advisory`: Warnungen protokollieren, Exit `0`, aber mit klarer Kennzeichnung.
- Diese Erweiterung braucht separate Tests und bewusstes Product-Decision-Record.
