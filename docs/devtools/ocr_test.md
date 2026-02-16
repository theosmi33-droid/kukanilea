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

OCR-Policy nur in der Sandbox aktivieren und direkt E2E testen:

```bash
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --json --timeout 30
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
- `sandbox_db_path` (nur gesetzt, wenn Sandbox aktiv und `--keep-artifacts` genutzt wird)
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
