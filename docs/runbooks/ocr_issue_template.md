# OCR Issue Template

## Zweck

Dieses Template stellt sicher, dass OCR-Probleme reproduzierbar und ohne PII
eskaliert werden.

## 1) Kommando ausfuehren

```bash
python -m app.devtools.cli_ocr_test \
  --tenant <TENANT_ID> \
  --doctor-and-sandbox \
  --write-support-bundle \
  --json
```

## 2) Bitte im Ticket angeben

- Zeitpunkt (UTC)
- verwendeter Tenant (synthetisch oder interne ID)
- Exit-Code (`0`, `1`, `2`)
- `reason` aus JSON
- exaktes CLI-Kommando (ohne Secrets)

## 3) Anhaenge

- `support_bundle.zip` (oder die einzelnen JSON-Dateien)
- falls vorhanden:
  - `docs/devtools/ocr_doctor_proof.json`
  - `docs/devtools/ocr_sandbox_e2e_proof.json`

## 4) Datenschutz

- Keine Rohdokumente anhaengen
- Keine SQLite-Dateien anhaengen
- Keine realen E-Mail-Adressen / Telefonnummern manuell in das Ticket kopieren
