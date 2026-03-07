Du arbeitest ausschließlich im Repo KUKANILEA.

MODUS
- Fix

ZIEL
- Behebe genau einen reproduzierbaren CI-Fehler aus GitHub Actions mit minimalem Patch.

SCOPE
- Erlaubt: direkt betroffene Dateien + zugehörige Tests.
- Verboten: pauschale CI-Umbauten, globale Refactors, kosmetische Massenänderungen.

MAIN-ONLY
- Arbeite auf `main`.
- Erstelle keine Branches.

ARBEITSWEISE
1) Fehler aus Check-Log extrahieren.
2) Root Cause benennen.
3) Minimal fixen.
4) Lokalen Repro-Test laufen lassen.

VALIDIERUNG
- betroffener Test/Check lokal reproduziert und grün
- optional: `bash scripts/ops/healthcheck.sh --strict-doctor --skip-pytest`

DOD
- Der konkrete Fehler ist reproduzierbar behoben.
- Kein Scope-Drift.

AUSGABEFORMAT
1. Analyse
2. Änderung
3. Validierung
4. Restrisiken
5. Abschluss

