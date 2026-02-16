# OCR Devtools — Definition of Done (DoD)

## Ziel

OCR-Devtools gelten als abnahmefaehig, wenn der Operator-Workflow reproduzierbar, deterministic und PII-sicher ist.

## Pflicht-Checks

1. Policy-Check laeuft:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-policy --json
```

2. Tesseract-Check laeuft:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --json
```

3. Doctor-Run in Sandbox laeuft:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --json
```

4. Strikter Doctor-Run (CI-Mode):
```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --strict --json
```

6. Optionaler Proof-Bundle-Export:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --json --write-proof --proof-dir docs/devtools
```

5. PII-Invariante:
- `pii_found_knowledge == false`
- `pii_found_eventlog == false`

## Exit-Code-Vertrag

- `0`: Erfolg
- `2`: `ok_with_warnings` ohne strict
- `1`: alle Fehler und strict-warning

## Failure-Matrix

| reason | Bedeutung | Next Actions |
|---|---|---|
| `policy_denied` | OCR policy fuer Tenant inaktiv | Sandbox-Enable nutzen (`--doctor` Standardpfad) oder Policy explizit setzen |
| `read_only` | Mutationspfad blockiert | READ_ONLY deaktivieren oder nur read-only Checks laufen lassen |
| `tesseract_missing` | Binary nicht verfuegbar/ungueltig | Installation/PATH pruefen, `--show-tesseract` ausfuehren |
| `tessdata_missing` | Sprachdaten nicht aufloesbar | `--tessdata-dir` setzen, `--list-langs` pruefen |
| `language_missing` | angeforderte Sprache fehlt | Sprache anpassen (`--lang`) oder Sprachdaten installieren |
| `timeout` | OCR-Lauf zu langsam/haengt | Timeout erhoehen, Scanner-Inbox prüfen |
| `job_not_found` | kein OCR-Job erzeugt | Watch-Config seeden, `--direct-submit-in-sandbox` nutzen |
| `config_file_missing` | Tesseract config loading Fehler | Installation pruefen, mit explizitem Tessdata erneut testen |
| `ok_with_warnings` | Lauf ok, aber Warnungen vorhanden | Warnungen beheben oder strict fuer CI aktivieren |
