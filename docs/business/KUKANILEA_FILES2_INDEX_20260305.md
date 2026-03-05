# KUKANILEA FILES2 INDEX (2026-03-05)

## Zweck
Dieser Index trennt klar zwischen **aktueller Wahrheit**, **nachgewiesenen Ergebnissen** und **Vision**.
So wird vermieden, dass Dokumente als „fertig implementiert“ missverstanden werden.

## Status-Tags (verbindlich)
- **[CANONICAL]** = aktuell gültige Referenz für Betrieb/Umsetzung.
- **[EVIDENCE]** = enthält überprüfbare Nachweise (Kommandos, Outputs, Artefakte).
- **[VISION]** = Zielbild/Planung; nicht automatisch implementierter Stand.

## Index (repo-relative Pfade)
| Status | Datei | Zweck |
|---|---|---|
| [CANONICAL] | `README.md` | Produktüberblick und Einstieg |
| [CANONICAL] | `ROADMAP.md` | priorisierte Umsetzungslinien |
| [CANONICAL] | `PROJECT_STATUS.md` | aktueller Projektstatus |
| [CANONICAL] | `docs/MASTER_INTEGRATION_PROMPT.md` | Integrationsleitplanken |
| [CANONICAL] | `docs/business/WELCOME_KIT.md` | Kunden-Onboarding-Text |
| [CANONICAL] | `docs/contracts/README.md` | Contract-Standards |
| [EVIDENCE] | `docs/reviews/codex/PR_BATCH_STATUS_20260304_1916.md` | PR-/Batch-Nachweise |
| [EVIDENCE] | `evidence/operations/` | Betriebsnachweise, Drill-Artefakte |
| [VISION] | `docs/vision/KUKANILEA_FINAL_MASTER_PLAN_v3.md` | strategisches Zielbild |
| [VISION] | `docs/vision/KUKANILEA_HARMONIE_INTEGRATIONSPFAD.md` | Integrationspfad/Architekturvision |
| [CANONICAL] | `docs/business/MARKET_EVIDENCE.md` | Marktbeleg-Backlog + Produktimplikationen |

## Pflege-Regeln
1. **Nur repo-relative Pfade** (keine lokalen/absoluten Pfade).
2. Neue strategische Dokumente müssen einen Status-Tag erhalten.
3. Bei Widersprüchen gilt: `[CANONICAL]` vor `[EVIDENCE]` vor `[VISION]`.
4. Evidence-Dokumente müssen reproduzierbare Nachweise enthalten.
