# Devtools OCR Test CLI

`app.devtools.cli_ocr_test` prueft den OCR-Workflow deterministisch:
- Policy-Zustand
- Tesseract-Binary-Verfuegbarkeit
- OCR-Job-Ausfuehrung ueber Source-Scan
- Redaction/PII-Leak-Checks in Knowledge und Eventlog

Der Test laeuft standardmaessig im Sandbox-Modus (temporare DB-Kopien).

## Beispiele

```bash
python -m app.devtools.cli_ocr_test --tenant dev
python -m app.devtools.cli_ocr_test --tenant dev --json
```

Ohne Sandbox (schreibt Jobs in die echte DB, nur fuer bewusstes Debugging):

```bash
python -m app.devtools.cli_ocr_test --tenant dev --no-sandbox
```

Artefakte im Sandbox-Lauf behalten:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --keep-artifacts
```

## Rueckgabe

`ok=true` bedeutet:
- Policy aktiv
- Tesseract gefunden
- OCR-Job erfolgreich
- keine PII-Patterns in Knowledge/Eventlog gefunden

`ok=false` liefert einen stabilen `reason` (z. B. `policy_denied`, `tesseract_missing`, `read_only`, `pii_leak`).
