# Gemini Reference Stack (KUKANILEA)

Diese Datei definiert den festen Kontext fuer Gemini-Sessions im KUKANILEA-Projekt.

## Prioritaets-Reihenfolge
1. `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_ALIGNMENT_PROMPT.md`
2. `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/TAB_OWNERSHIP_RULES.md`
3. `/Users/gensuminguyen/Downloads/files/KUKANILEA_CLI_MASTER_ANLEITUNG.md`
4. `/Users/gensuminguyen/Downloads/files/KUKANILEA_FINAL_MASTER_PLAN_v3.md`
5. `/Users/gensuminguyen/Downloads/files/KUKANILEA_HARMONIE_INTEGRATIONSPFAD.md`
6. `/Users/gensuminguyen/Downloads/files/KUKANILEA_TEAM_1PAGER.md`
7. `/Users/gensuminguyen/Downloads/files/SOVEREIGN_11_FINAL_PACKAGE.md`
8. `/Users/gensuminguyen/Downloads/files/SOVEREIGN_11_QUICK_ACTION_CHECKLIST.md`
9. `/Users/gensuminguyen/Downloads/files/SCOPE_REQUEST_EXAMPLE_DASHBOARD.md`

## Arbeitsregeln fuer Gemini
- Domain-Exklusivitaet strikt einhalten (keine Shared-Core Edits ohne Scope-Request).
- Zero-CDN und White-Mode-only beibehalten.
- HTMX-Shell-Kontrakt respektieren (`hx-get`, `hx-target`, `hx-push-url`).
- Bei Empfehlungen immer Bezug auf mindestens eine Datei aus der Prioritaetsliste nennen.
- Bei Unsicherheit zuerst die Referenzdateien lesen, dann erst aendern.

## Standard-Ausgabeformat fuer Reviews
- `Status: PASS | PASS with notes | FAIL`
- `Gepruefte Dateien`
- `Tests und Ergebnis`
- `Risiken/Blocker`
- `Naechster konkreter Schritt`
