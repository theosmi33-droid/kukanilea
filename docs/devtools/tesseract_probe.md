# Devtools — Tesseract Probe

## Zweck
`app/devtools/tesseract_probe.py` liefert eine deterministische Preflight-Diagnose fuer OCR:
- Binary-Aufloesung (`tesseract`)
- Tessdata-Aufloesung (Prefix/Verzeichnis)
- Verfuegbare Sprachen via `--list-langs`
- Konsistente Reason-Codes + Next-Actions

## Ablauf (Kurz)
1. Binary aufloesen (projektinterne Resolver-Logik, dann PATH-Fallback).
2. Tessdata-Kandidaten in stabiler Reihenfolge pruefen.
3. `tesseract --list-langs` ausfuehren (optional mit `--tessdata-dir`).
4. Sprache waehlen:
   - explizit `--lang`, falls vorhanden
   - sonst bevorzugt `eng`
   - sonst erster nicht-`osd` Eintrag
5. Fehler klassifizieren:
   - `tesseract_missing`
   - `tessdata_missing`
   - `language_missing`
   - `tesseract_failed`

## Sanitizing
- `stderr_tail` wird bereinigt:
  - absolute Pfade -> `<path>`
  - bekannte Testmarker -> `<redacted>`
- Ziel: keine PII und keine lokalen User-Pfade in CLI-Ausgabe.

## CLI Nutzung
```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --json
```

Mit explizitem Tessdata/Lang:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --tessdata-dir /path/to/tessdata --lang eng --json
```

## Output-Hinweise
- `tessdata_dir` / `tessdata_prefix_used`: sanitisiert
- `tesseract_langs`: deterministische Liste
- `tesseract_lang_used` / `lang_used`: effective language
- `tesseract_probe_reason` / `probe_reason`: Diagnose-Code
- `next_actions`: konkrete naechste Schritte fuer Operator

