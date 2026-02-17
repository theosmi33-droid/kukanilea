# OCR Doctor (Operator/DevOps)

`app.devtools.cli_ocr_test --doctor` ist der konsolidierte Operator-Check fuer OCR:

- Policy-Status (Base-DB)
- Tesseract-Probe (Version, Langs, Tessdata-Discovery)
- Deterministischer Sandbox-E2E-Smoke (Policy + Watch-Config + optional Direct-Submit)
- Optionale, explizit abgesicherte Real-DB-Policy-Aktivierung
- Operator-Bootstrap-Hinweise (`install_hints`, `config_hints`) fuer die
  Faelle `tesseract_missing`, `tesseract_not_allowlisted`, `tesseract_exec_failed`, `tessdata_missing`, `language_missing`
- Strukturierte Operator-Hints in `operator_hints` (OS, Probe-Zusammenfassung,
  sanitisiertes Hint-Set)
- Probe- und Job-Resolver sind vereinheitlicht (gleiche Allowlist-/Prefix-Regeln)

## Sicherheitsmodell

- Standard: `sandbox=on` (keine Mutation in der echten DB)
- Keine neuen Dependencies, kein Netzwerk
- Tenant-gebunden (`--tenant` ist Pflicht)
- READ_ONLY blockiert alle Mutationspfade
- Ausgabe ist sanitisiert (keine absoluten User-Pfade, keine PII-Marker)

## Exit-Codes

- `0`: Erfolg
- `2`: `ok_with_warnings` (nur ohne `--strict`)
- `1`: alle Fehler (inkl. strict-warning, policy_denied, read_only)

## Empfohlener Ablauf

```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --json
python -m app.devtools.cli_ocr_test --tenant dev --doctor --strict --json
python -m app.devtools.cli_ocr_test --tenant dev --doctor --doctor-only --json
python -m app.devtools.cli_ocr_test --tenant dev --doctor --doctor-and-sandbox --json
```

Runtime-Overrides fuer den Jobpfad (optional):
- `AUTONOMY_OCR_TESSERACT_BIN`
- `AUTONOMY_OCR_TESSDATA_DIR`
- `AUTONOMY_OCR_LANG`

Readiness-Felder fuer OCR-v0 (introspektiv, ohne DB-Mutation):

- `ocr_v0_present`
- `ocr_v0_tables_present`
- `ocr_v0_pipeline_callable`
- `ocr_v0_missing_tables`
- `ocr_v0_next_actions`

Mit Report-Artefakten:

```bash
python -m app.devtools.cli_ocr_test \
  --tenant dev \
  --doctor \
  --json \
  --report-json-path reports/ocr_doctor.json \
  --report-text-path reports/ocr_doctor.txt
```

Proof-Bundle (sanitisierte DoD-Artefakte im Repo):

```bash
python -m app.devtools.cli_ocr_test \
  --tenant dev \
  --doctor \
  --json \
  --write-proof \
  --proof-dir docs/devtools
```

Erzeugte Dateien:
- `docs/devtools/ocr_doctor_proof.json`
- `docs/devtools/ocr_sandbox_e2e_proof.json`

Support-Bundle (sanitisiert, schema-only, ohne DB/Datei-Inhalte):

```bash
python -m app.devtools.cli_ocr_test \
  --tenant dev \
  --doctor-and-sandbox \
  --write-support-bundle \
  --json
```

Optional:
- `--bundle-dir <dir>`
- `--zip-bundle` / `--no-zip-bundle`

## Optional: reale Policy-Aktivierung (explizit)

Dieser Pfad ist absichtlich stark abgesichert:

- `--commit-real-policy`
- `--yes-really-commit <TENANT_ID>` mit exakt gleicher Tenant-ID
- READ_ONLY muss `false` sein

Beispiel:

```bash
python -m app.devtools.cli_ocr_test \
  --tenant dev \
  --doctor \
  --commit-real-policy \
  --yes-really-commit dev \
  --json
```

Wenn Guard-Bedingungen nicht passen, endet der Lauf mit `reason=commit_guard_failed` oder `reason=read_only`.
