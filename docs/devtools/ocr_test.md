# Devtools OCR Test CLI

`app.devtools.cli_ocr_test` prueft den OCR-Workflow deterministisch:
- Policy-Zustand
- Tesseract-Binary-Verfuegbarkeit
- OCR-Job-Ausfuehrung ueber Source-Scan
- Redaction/PII-Leak-Checks in Knowledge und Eventlog

Der Test laeuft standardmaessig im Sandbox-Modus (temporare DB-Kopien).
Sandbox bedeutet: Die echte Core-DB wird 1:1 kopiert, der Test laeuft nur auf der Kopie.

## Beispiele

```bash
python -m app.devtools.cli_ocr_test --tenant dev
python -m app.devtools.cli_ocr_test --tenant dev --json
```

Nur Policy lesen (kein OCR-Run):

```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-policy --json
```

Nur Tesseract-Diagnostik (ohne OCR-Run):

```bash
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --json
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --tessdata-dir /path/to/tessdata --lang eng --json
python -m app.devtools.cli_ocr_test --tenant dev --show-tesseract --strict --json
```

OCR-Policy nur in der Sandbox aktivieren und direkt E2E testen:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --json --timeout 30
```

Deterministischer Smoke mit Watch-Config-Seeding + optionalem Direkt-Submit:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --json --timeout 30 --seed-watch-config-in-sandbox
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --json --timeout 30 --direct-submit-in-sandbox
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --json --timeout 30 --strict
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --json --timeout 30 --no-retry
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
Zusaetzliche Felder fuer Operator-Diagnose:
- `policy_enabled_base`
- `policy_enabled_effective`
- `policy_reason`
- `existing_columns`
- `tessdata_dir`, `tessdata_source`
- `tessdata_prefix_used`
- `tesseract_langs`, `tesseract_lang_used`
- `tesseract_warnings`
- `tesseract_probe_reason`, `tesseract_probe_next_actions`, `tesseract_stderr_tail`
- `lang_used`, `probe_reason`, `probe_next_actions`, `stderr_tail`
- `strict_mode`, `retry_enabled`, `tesseract_retry_used`, `lang_fallback_used`, `tessdata_fallback_used`
- `sandbox_db_path` (nur gesetzt, wenn Sandbox aktiv und `--keep-artifacts` genutzt wird)
- `watch_config_seeded`, `watch_config_existed`
- `inbox_dir_used`, `scanner_discovered_files`
- `direct_submit_used`
- `next_actions`

## OCR fuer Tenant `dev` aktivieren (lokal)

Die OCR-Policy wird in der Tabelle `knowledge_source_policies` gespeichert.
Fuer den End-to-End-Lauf ueber den Scanner werden diese Flags benoetigt:
- `allow_ocr = 1` (direkter OCR-Gate aus `ocr_allowed(tenant_id)`)
- `allow_documents = 1` (Dokument-Ingest aktiv)
- `allow_customer_pii = 1` (Dokument-Quelle darf persistieren)

Beispiel (lokale Core-DB):

```bash
sqlite3 "${KUKANILEA_CORE_DB:-$HOME/Library/Application Support/KUKANILEA/core.sqlite3}" <<'SQL'
INSERT INTO knowledge_source_policies(
  tenant_id,
  allow_manual,
  allow_tasks,
  allow_projects,
  allow_documents,
  allow_leads,
  allow_email,
  allow_calendar,
  allow_ocr,
  allow_customer_pii,
  updated_at
) VALUES (
  'dev', 1, 1, 1, 1, 0, 0, 0, 1, 1, datetime('now')
)
ON CONFLICT(tenant_id) DO UPDATE SET
  allow_documents=1,
  allow_ocr=1,
  allow_customer_pii=1,
  updated_at=datetime('now');
SQL
```

Alternative ohne echte DB-Mutation:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --json
```

READ_ONLY-Verhalten:
- Wenn READ_ONLY aktiv ist, fuehrt das Tool nur Preflight aus und bricht mit `reason=read_only` ab.
- In READ_ONLY werden keine Ingest-/OCR-Mutationen gestartet.
- In READ_ONLY wird auch `--enable-policy-in-sandbox` verweigert (`reason=read_only`).

Verifikation:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --json --timeout 15
```

Erwartung nach Aktivierung:
- `policy_enabled: true`
- `reason` ist nicht mehr `policy_denied`
- bei verfuegbarem Tesseract wird `tesseract_found: true`

## Troubleshooting (`reason` -> `next_actions`)

- `policy_denied`
  - OCR-Policy fuer Tenant aktivieren (`--enable-policy-in-sandbox`).
  - Tenant-ID pruefen.
- `tesseract_missing`
  - Tesseract installieren und PATH pruefen.
  - Erneut mit `--json` laufen lassen und `tesseract_found=true` verifizieren.
- `tessdata_missing`
  - `--tessdata-dir` explizit setzen.
  - Sicherstellen, dass passende `*.traineddata` Dateien vorhanden sind.
- `language_missing`
  - Gewuenschte Sprache mit `--lang` pruefen.
  - Fehlende Sprachdaten installieren oder auf verfuegbare Sprache wechseln.
- `ok_with_warnings`
  - OCR-Umgebung funktioniert, aber mit Warnungen (z. B. fehlende optionale Sprachdaten).
  - Fuer harte CI/Smoke-Laeufe `--strict` verwenden.
- `tesseract_warning`
  - `--strict` hat `ok_with_warnings` als Fehler behandelt.
  - Warnungen beheben oder Strict-Mode fuer lokale Diagnose deaktivieren.
- `tesseract_failed`
  - `--show-tesseract` laufen lassen und `tesseract_stderr_tail` auswerten.
- `read_only`
  - READ_ONLY im Dev-Setup deaktivieren oder nur `--show-policy` nutzen.
- `watch_config_table_missing`
  - Autonomy-Tabellen initialisieren (`source_watch_config` fehlt).
- `job_not_found`
  - Mit `--seed-watch-config-in-sandbox` laufen lassen.
  - Optional `--direct-submit-in-sandbox` aktivieren.
- `source_files_table_missing` / `source_files_schema_unknown`
  - Scanner-Schema pruefen (`source_files` + Spalten wie `path_hash`/`basename`).
- `failed`
  - Lokale Tesseract-Installation und Sprachdaten pruefen.
  - Erneut mit `--direct-submit-in-sandbox` starten und `job_error_code` auswerten.
- `pii_leak`
  - Sofort stoppen; Redaction/Eventlog-Pfad regressionspruefen.

Hinweis:
- Fuer reproduzierbare Diagnostik wird `--tessdata-dir` bevorzugt statt implizitem `TESSDATA_PREFIX`.
- Detaillierte Probe-Logik: `docs/devtools/tesseract_probe.md`.

Manuelle Triage:
```bash
tesseract --version
tesseract --list-langs --tessdata-dir <dir>
```
