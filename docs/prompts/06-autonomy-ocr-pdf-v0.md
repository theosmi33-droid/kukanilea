# CODEX-PROMPT - Autonomy Phase 2c: PDF-OCR mit pdftoppm + Tesseract

```text
Repo: <REPO_ROOT>
Base branch: main (nach Merge von autonomy-phase2a-tags-metadata)
Branch: codex/feat/autonomy-ocr-pdf-v0

ZIEL
Erweitere die bestehende OCR-Pipeline um PDF-Unterstuetzung:
- Nutzer kann PDF-Dateien in den Ingest-Ordner legen.
- Bei aktivierter Policy `allow_pdf_ocr` wird das PDF mit `pdftoppm` in Bilder konvertiert (nur die ersten N Seiten).
- Pro Seite wird die bestehende Tesseract-Pipeline aufgerufen (gleiche Limits, Redaktion).
- Der extrahierte Text aller Seiten wird zusammengefasst und als ein Knowledge-Chunk (source_type='pdf_ocr') gespeichert.
- Alle Operationen sind tenant-isoliert, READ_ONLY-sicher, PII-frei im Eventlog und ohne neue Python-Dependencies.

HARTE LEITPLANKEN
- Keine neuen Python-Dependencies.
- Kein Netzwerk.
- Keine Shell/Subprocess mit `shell=True`.
- `pdftoppm` und `tesseract` werden ueber `shutil.which` gefunden und muessen in Allowlist-Verzeichnissen liegen.
- Keine Benutzereingaben als Argumente (Sprache, Optionen) - alles hart kodiert oder aus Config.
- Keine Seitenzahlpruefung vorab - stattdessen werden nur die ersten `max_pages` Seiten konvertiert (`pdftoppm -f 1 -l MAX_PAGES`). Falls `MAX_PAGES` Seiten erzeugt werden, wird ein `truncated`-Flag gesetzt (es koennten mehr existieren).
- Feste Render-DPI (z.B. `-r 150`) und Pixel-Limits (`max_total_pixels` ueber geschaetzte Bildgroesse).
- Tempfiles werden sicher geloescht (auch bei Fehlern).
- Eventlog PII-frei (nur IDs, Dauer, Seitenzahl, Status, `truncated`-Flag).
- READ_ONLY blockiert alle OCR-Trigger.

A) SCHEMA (additiv, idempotent) - kukanilea_core_v3_fixed.py
A1) knowledge_source_policies: neue Spalte `allow_pdf_ocr` (INTEGER NOT NULL DEFAULT 0)
- Idempotent via `_add_column_if_missing`.

A2) Neue Tabelle `autonomy_pdf_ocr_jobs` (separat, um Monitoring zu vereinfachen)
CREATE TABLE IF NOT EXISTS autonomy_pdf_ocr_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source_file_id TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    pages_processed INTEGER,
    truncated INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    chars_out INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_file_id) REFERENCES source_files(id)
);

Indizes:
CREATE INDEX IF NOT EXISTS idx_pdf_ocr_jobs_tenant_created ON autonomy_pdf_ocr_jobs(tenant_id, created_at DESC);

B) CORE - app/autonomy/ocr.py erweitern
B1) Neue Funktion `pdf_allowed(tenant_id) -> bool` (liest `allow_pdf_ocr`).

B2) `resolve_pdftoppm_bin() -> str | None` (analog zu `resolve_tesseract_bin`).

B3) `pdf_to_images(pdf_path: Path, max_pages: int, fixed_dpi: int, timeout_per_page: int) -> tuple[List[Path], int, bool]`:
- Nutzt `pdftoppm` mit `-f 1 -l {max_pages} -r {fixed_dpi} -png` (oder -tiff), erzeugt temporaere PNG-Dateien.
- Liefert (Liste der Bildpfade, tatsaechliche Seitenanzahl, truncated_flag).
- Truncated_flag = True wenn tatsaechliche Seitenanzahl == max_pages.
- Setzt globalen Timeout und faengt `subprocess.TimeoutExpired` ab.

B4) `submit_ocr_for_source_file` wird erweitert:
- Wenn Dateiendung `.pdf` und `pdf_allowed()` -> neuer PDF-OCR-Job.
- Prueft `max_pdf_bytes` vor der Verarbeitung.
- Ruft `pdf_to_images` auf.
- Fuer jedes Bild: `_run_tesseract` (mit denselben Limits wie bei Bild-OCR).
- Sammelt Ergebnisse, redigiert sie (`knowledge_redact_text`), erstellt einen Knowledge-Chunk (source_type='pdf_ocr').
- Job-Status aktualisieren: `status='done'`, `pages_processed`, `truncated`, `chars_out`.
- Bei Fehlern wird der gesamte Job als `failed` markiert (fail-fast).
- Tempfiles garantiert loeschen (`try/finally` oder `tempfile.TemporaryDirectory`).

B5) Limits (Konfiguration via Env/Config mit Min/Max-Pruefung):
- `AUTONOMY_PDF_MAX_BYTES` (default 25 MB)
- `AUTONOMY_PDF_MAX_PAGES` (default 5)
- `AUTONOMY_PDF_FIXED_DPI` (default 150)
- `AUTONOMY_PDF_PAGE_TIMEOUT` (default 30 s)
- `AUTONOMY_PDF_GLOBAL_TIMEOUT` (default 300 s)

C) TESTS (mit Mocks fuer pdftoppm und tesseract)
1. Policy Default-Deny: PDF-Upload -> skipped_policy.
2. pdftoppm fehlt: `resolve_pdftoppm_bin` mockt None -> Job fehlschlaegt mit `pdftoppm_missing`.
3. PDF zu gross -> `error_code='too_large'`.
4. PDF mit 10 Seiten, `max_pages=5` -> `pages_processed=5`, `truncated=1`, Job done.
5. Erfolgreiches PDF mit 2 Seiten -> beide Seiten verarbeitet, Text zusammengefasst, Chunk erzeugt.
6. Timeout pro Seite -> `error_code='pdf_page_timeout'`.
7. Eventlog-Payload enthaelt nur IDs, `pages_processed`, `truncated`, `duration_ms`, `chars_out`, keine Pfade/Dateinamen.
8. Tempdir-Cleanup: Bei Exception werden Tempfiles geloescht.
9. READ_ONLY blockiert.

D) DOKUMENTATION + ADR
- `docs/autonomy_ocr_pdf_v0.md` - Setup, Limits, Sicherheitsmassnahmen.
- `docs/decisions/0022-pdf-ocr-v0.md` - Entscheidung.

QUALITY GATES
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings \
  --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"

COMMIT
git checkout -b codex/feat/autonomy-ocr-pdf-v0
git add kukanilea_core_v3_fixed.py app/autonomy/ocr.py app/autonomy/__init__.py tests/ docs/
git commit -m "feat(autonomy): add PDF OCR support with pdftoppm (first N pages, truncated flag)"
git push -u origin codex/feat/autonomy-ocr-pdf-v0
```
