# Autonomy OCR v0

Autonomy OCR v0 erweitert den lokalen Source-Scanner um optionales OCR fuer Bilddateien.

## Scope
- OCR ist policy-gated (`knowledge_source_policies.allow_ocr`, Default `0`).
- Unterstuetzte Formate: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`.
- PDF-OCR ist in v0 explizit nicht enthalten (`pdf_not_supported`).
- Keine neuen Dependencies, kein Netzwerk.

## Sicherheitsmodell
- Tesseract wird nur ueber `subprocess.run` mit Argumentliste aufgerufen.
- `shell=False`, `stdin=DEVNULL`, harter Timeout.
- Binary-Aufloesung nur via `shutil.which("tesseract")` und absolute, allowlisted Pfade.
- Eventlog bleibt PII-frei (keine Dateinamen, keine Pfade, kein OCR-Text).

## Limits
- `AUTONOMY_OCR_MAX_BYTES` (Default `10MB`)
- `AUTONOMY_OCR_TIMEOUT_SEC` (Default `30`)
- `AUTONOMY_OCR_MAX_CHARS` (Default `200000`, danach Truncate)
- `AUTONOMY_OCR_LANG` (Default `eng`, Regex-validiert)

## Verarbeitung
1. Scanner ingestiert die Quelldatei wie bisher.
2. Bei Bilddateien wird OCR best-effort gestartet.
3. OCR-Text wird vor Speicherung verpflichtend redigiert.
4. Redigierter Text wird als `knowledge_chunks.source_type='ocr'` gespeichert.
5. Job-Status wird in `autonomy_ocr_jobs` protokolliert.

## Health/Observability
- `/autonomy/health` zeigt letzte OCR-Jobs und 24h-Statuszahlen.
- Jobstatus: `pending`, `processing`, `done`, `failed`, `skipped`.
- Fehlercodes: z. B. `policy_denied`, `too_large`, `timeout`, `tesseract_missing`.
