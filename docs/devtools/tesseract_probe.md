# Devtools — Tesseract Probe v4

## Zweck
`app/devtools/tesseract_probe.py` liefert eine robuste, deterministische Diagnose fuer OCR-Preflight:
- Binary-Aufloesung (`tesseract`)
- Tessdata-Kandidaten (inkl. Prefix-Normalisierung)
- Feature-Detection fuer optionale Flags (insbesondere `--print-tessdata-dir`)
- `--print-tessdata-dir` als priorisierte Quelle fuer tessdata (wenn unterstuetzt)
- Sprachliste via `--list-langs`
- stabile Reason-Codes + Next-Actions

## Reason-Codes
- `ok`
- `ok_with_warnings`
- `tesseract_missing`
- `tessdata_missing`
- `language_missing`
- `tesseract_failed`

## Verhalten
1. Binary wird aufgeloest (projektinterner Resolver, dann PATH-Fallback).
2. Tessdata-Kandidaten werden in stabiler Reihenfolge gebaut:
   - `tesseract --print-tessdata-dir` (nur wenn Flag unterstuetzt ist)
   - CLI (`--tessdata-dir`)
   - `TESSDATA_PREFIX`
   - Bin-heuristiken + Systempfade
3. Probe laeuft ueber `tesseract --list-langs`.
4. Parsing ist warning-tolerant:
   - Wenn `stdout` gueltige Sprachen enthaelt, bleibt Probe nutzbar
   - `stderr`-Warnungen fuehren zu `ok_with_warnings` statt Hartabbruch
   - Sprachcodes erlauben auch Unterstriche, z. B. `chi_sim`, `aze_cyrl`, `deu_frak`
5. Sprachwahl:
   - explizit requested language
   - sonst `eng`
   - sonst erster nicht-`osd`

## Sanitizing
- `warnings` und `stderr_tail` werden PII-/Pfad-sicher bereinigt:
  - bekannte Marker -> `<redacted>`
  - absolute Pfade -> `<path>`
  - harte Laengenlimits

## CLI-Beispiele
```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --json
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --tessdata-dir /path/to/tessdata --lang eng --json
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --tesseract-bin /path/to/tesseract --json
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --strict --json
```

Manuelle Operator-Pruefung:
```bash
tesseract --version
tesseract --list-langs --tessdata-dir <dir>
```

## Referenzen
- [Tesseract Manpage (Debian)](https://manpages.debian.org/buster/tesseract-ocr/tesseract.1.en.html)
- [Tesseract Command-Line Usage](https://github.com/tesseract-ocr/tesseract/wiki/Command-Line-Usage)
