# Fleet 11-Tab Master Status

- Timestamp: 2026-03-03T19:55:02+01:00
- Branch: main
- Healthcheck: PASS
- Overlap Matrix: docs/reviews/codex/OVERLAP_MATRIX_11_20260303_195251.md

## Domain Table

| Domain | Branch | Dirty | Diff vs main | Overlap |
|---|---|---:|---:|---|
| dashboard | codex/dashboard | 0 | 4 | OK |
| upload | codex/upload | 0 | 0 | OK(no_diff) |
| emailpostfach | codex/emailpostfach | 0 | 0 | OK(no_diff) |
| messenger | codex/messenger | 0 | 0 | OK(no_diff) |
| kalender | codex/kalender | 0 | 0 | OK(no_diff) |
| aufgaben | codex/aufgaben | 0 | 0 | OK(no_diff) |
| zeiterfassung | codex/zeiterfassung | 0 | 2 | OK |
| projekte | codex/projekte | 0 | 0 | OK(no_diff) |
| excel-docs-visualizer | codex/excel-docs-visualizer | 0 | 3 | OK |
| einstellungen | codex/einstellungen | 0 | 0 | OK(no_diff) |
| floating-widget-chatbot | codex/floating-widget-chatbot | 0 | 2 | OK |

## Top 5 Blocker

1. Keine P0-Blocker offen (Healthcheck gruen).
2. Overlap-Check ist fuer alle 11 Domains OK.
3. Guardrail-Drift behoben (CDN entfernt, hx-confirm ergaenzt).
4. Floating-Widget unowned untracked files bereinigt (Backup unter docs/reviews/codex/_backup_floating_unowned_20260303_1953).
5. Overlap-Script korrigiert auf branch-only Delta (main...HEAD), um False Positives zu vermeiden.

## Naechste 3 Integrationsschritte

1. Open PR von local main gegen origin/main vorbereiten (kein force push).
2. Optional: Stash `tmp-scope-patches-20260303` pruefen und relevante Patch-Artefakte gezielt uebernehmen.
3. CI/Actions Lauf nach Push beobachten und nur rote Jobs gezielt fixen.

## Healthcheck Tail

```text
  [6/7] DB sanity check...
  [7/7] Verifying guardrails (CDN & HTMX confirm)...
  [GUARDRAIL] Verifying CDN and HTMX confirm gates...
  OK: All guardrail checks passed.
  [healthcheck] All checks passed
```
