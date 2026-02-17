# Text-ID Migration Plan (Phased, Low-Risk)

Stand: 2026-02-17

## Ziel
Legacy `INTEGER PRIMARY KEY AUTOINCREMENT` Tabellen kontrolliert auf `TEXT PRIMARY KEY` umstellen, ohne History-Rewrite und ohne Big-Bang Risiko.

## Phase 0: Faktenbasis herstellen
1. Schema audit ausfuehren:
```bash
python -m app.devtools.schema_audit --json > reports/schema_audit.json
```
2. Findings nach Risiko clustern:
- A: produktionskritische Tabellen mit tenant Daten
- B: interne/systemnahe Tabellen
- C: bench/test-only Tabellen

## Phase 1: Neue Entwicklung auf TEXT-ID erzwingen
- Neue Tabellen nur mit `id TEXT PRIMARY KEY`.
- Jede neue fachliche Tabelle mit `tenant_id`.
- PR-Review mit `docs/PR_REVIEW_CHECKLIST.md` verpflichtend.

## Phase 2: Kompatibilitaetsmigration pro Tabelle
Je Tabelle in separatem PR:
1. Additiv `id_text` Spalte einfuehren.
2. Backfill `id_text` fuer alle Zeilen.
3. Referenzierende Tabellen um parallele `*_id_text` Spalten erweitern.
4. Read-Pfade dual unterstuetzen (alt + neu).
5. Write-Pfade dual schreiben.
6. Regressionstests tenant-safe erweitern.

## Phase 3: Cutover
Je Tabelle nach stabiler Kompatibilitaetsphase:
1. Primarzugriff nur noch ueber TEXT-ID.
2. API/Route/Service Signaturen auf TEXT-ID konsolidieren.
3. Audit-Belege in PR dokumentieren (before/after queries, smoke tests).

## Phase 4: Cleanup
- Legacy Integer-Pfade erst nach zwei stabilen Releases entfernen.
- Cleanup nur, wenn:
  - keine offenen Referenzen auf Integer-ID,
  - alle Metriken und CI-Gates gruen,
  - Rollback dokumentiert.

## Rollback-Strategie
- Bei Problemen Cutover PR revertieren.
- Kompatibilitaetspfad bleibt erhalten, daher kein Datenverlust durch sofortigen Revert.

## Mindestnachweis je Migrations-PR
- `python -m compileall -q .`
- `ruff check . --fix`
- `ruff format .`
- `pytest -q`
- `python -m app.devtools.schema_audit --fail-on-findings` (falls Zieltabellen voll umgestellt)
- `python -m app.devtools.triage --ci --fail-on-warnings --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"`
