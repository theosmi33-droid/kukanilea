# Tesseract Setup (Operator Runbook)

## Ziel

Dieses Runbook behebt die OCR-Doctor-Fehler:

- `tesseract_missing`
- `tesseract_not_allowlisted`
- `tessdata_missing`
- `language_missing`

Die Schritte sind rein operativ (keine Codeaenderung, keine Auto-Installation).

## 1) Binary pruefen

```bash
tesseract --version
```

Wenn der Befehl nicht gefunden wird:

- macOS: `brew install tesseract`
- Linux: Installation ueber den jeweiligen Paketmanager (z. B. apt/yum)
- Windows: Tesseract installieren und Binary-Verzeichnis in `PATH` aufnehmen

Alternativ im Tool explizit setzen:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --tesseract-bin <binary> --json
```

Wenn das Binary gefunden wird, aber `tesseract_not_allowlisted` gemeldet wird:

- Installationspfad in einen erlaubten Prefix legen (z. B. `/opt/homebrew`, `/usr/local/bin`, `/usr/bin`)
- Oder sichere Prefix-Erweiterung setzen:

```bash
export KUKANILEA_TESSERACT_ALLOWED_PREFIXES="/opt/homebrew:/usr/local/bin"
```

Wichtig: Niemals Root-Prefixe setzen (`/`, `C:\\`).

## 2) Sprachdaten pruefen

```bash
tesseract --list-langs --tessdata-dir <dir>
```

Hinweis: `--list-langs` kann Warnungen auf `stderr` ausgeben und trotzdem nutzbare
Sprachen liefern. Der Doctor behandelt das als `ok_with_warnings`.

Optional (wenn vom Binary unterstuetzt):

```bash
tesseract --print-tessdata-dir
```

## 3) OCR-Doctor ausfuehren

```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --json
```

Nur Diagnose ohne Sandbox-E2E:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --doctor-only --json
```

Bei fehlenden Sprachdaten mit explizitem Verzeichnis:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --tessdata-dir <dir> --json
```

Bei expliziter Sprache:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --lang eng --json
```

## 4) Proof-Artefakte (optional)

```bash
python -m app.devtools.cli_ocr_test \
  --tenant dev \
  --doctor \
  --json \
  --write-proof \
  --proof-dir docs/devtools
```

Erwartete Dateien:

- `docs/devtools/ocr_doctor_proof.json`
- `docs/devtools/ocr_sandbox_e2e_proof.json`

Support-Bundle fuer Tickets:

```bash
python -m app.devtools.cli_ocr_test \
  --tenant dev \
  --doctor-and-sandbox \
  --write-support-bundle \
  --json
```
