Mode: REVIEW_ONLY (strict). Do not edit files. Do not commit. Do not push.

Auftrag:
1) Prüfe alle 11 Worktrees unter /Users/gensuminguyen/Kukanilea/worktrees auf:
   - git clean status
   - branch korrekt (codex/<domain>)
   - Overlap-Status via scripts/dev/check_domain_overlap.py
2) Gib eine Matrix pro Domain mit PASS/FAIL und Blocker.
3) Erstelle einen mechanischen Remediation-Plan (nur Plan, keine Edits).

Domain-Liste:
- dashboard, upload, emailpostfach, messenger, kalender, aufgaben,
  zeiterfassung, projekte, excel-docs-visualizer, einstellungen, floating-widget-chatbot

Ausgabeformat:
- Matrix (Domain | Clean | Overlap | Blocker)
- P0/P1/P2
- Schrittfolge zur Finalisierung
