# ADR 0022: PDF-OCR (Phase 2c)

## Status
Draft

## Datum
2026-02-16

## Entscheider
KUKANILEA-Team

## Kontext
Die Pilotphase hat gezeigt, dass Nutzer haeufig PDF-Dokumente durchsuchen moechten. Tesseract kann keine PDFs direkt verarbeiten; es wird ein Zwischenschritt benoetigt, der PDF-Seiten in Bilder konvertiert. Dafuer bietet sich `pdftoppm` aus der Poppler-Suite an (verbreitet, stabil, als Binary verfuegbar). Die bereits bestehende OCR-Pipeline (Tesseract, Redaction, Eventlog) soll erweitert werden, ohne neue Python-Dependencies einzufuehren.

## Entscheidung
- PDF-OCR wird als **opt-in** pro Tenant umgesetzt (Policy `allow_pdf_ocr`, default `0`).
- Fuer die Konvertierung wird `pdftoppm` verwendet (Subprocess, `shell=False`, Allowlist-Pruefung des Pfades).
- Wir konvertieren und OCRen maximal die ersten `AUTONOMY_PDF_MAX_PAGES` Seiten (`pdftoppm -f 1 -l MAX_PAGES -r FIXED_DPI`). Falls `MAX_PAGES` Seiten erzeugt werden, setzen wir ein `truncated`-Flag (es koennten mehr existieren). Dadurch sind CPU/IO/Temp-Speicher deterministisch begrenzt, ohne zusaetzliche Parser/Dependencies.
- Feste Render-DPI (z.B. 150) und Seitengroessenlimits werden verwendet.
- Keine neuen Python-Dependencies - alle Aufrufe ueber Subprocess zu systemweit installierten Binaries.
- **Sicherheit**:
  - `pdftoppm`-Pfad wird ueber `shutil.which` und Allowlist validiert.
  - Aufruf mit fester Argument-Liste (keine Benutzereingaben als Argumente).
  - Temporaerdateien werden in einem sandboxed Tempdir angelegt und nach Bearbeitung geloescht.
  - Eventlog-Payloads bleiben PII-frei (nur IDs, Dauer, Seitenzahl, `truncated`).

## Konsequenzen
- Erweiterung von `knowledge_source_policies` um `allow_pdf_ocr`.
- Neue Tabelle `autonomy_pdf_ocr_jobs` (separat fuer einfaches Monitoring; langfristig koennte eine gemeinsame `ocr_jobs`-Tabelle mit `type`-Spalte sinnvoll sein).
- Bestehende `submit_ocr_for_source_file` wird um einen PDF-Zweig erweitert.
- Zusaetzliche Tests fuer PDF-Faelle.
- Dokumentation in `docs/autonomy_ocr_v0.md` wird erweitert.
