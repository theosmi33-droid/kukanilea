# OCR Policy Helper (Devtools)

`app.devtools.ocr_policy` bietet schema-sichere Hilfen fuer OCR-Policy-Checks in lokalen DBs.

## Funktionen

- `get_policy_status(tenant_id, db_path=...)`
  - introspektiert `knowledge_source_policies` ueber `PRAGMA table_info`.
  - erlaubt nur OCR-Flags aus der Allowlist:
    - `allow_ocr`
    - `ocr_enabled`
    - `ocr_allowed`
  - liefert deterministische Gruende bei Schema-Abweichungen:
    - `schema_unknown`
    - `ambiguous_columns`

- `enable_ocr_policy_in_db(tenant_id, db_path=..., confirm=True, read_only=False)`
  - setzt OCR-Policy auf `1` fuer den Tenant.
  - verweigert Writes bei `read_only=True` mit `reason=read_only`.
  - nutzt nur die uebergebene DB-Datei (z. B. Sandbox-Kopie).

- `ensure_watch_config_in_sandbox(tenant_id, sandbox_db_path=..., inbox_dir=...)`
  - prueft `source_watch_config` per Laufzeit-Introspection.
  - nutzt eine strikte Path-Spalten-Allowlist:
    - `documents_inbox_dir`
    - `inbox_dir`
    - `watch_dir`
    - `path`
  - schreibt/aktualisiert nur in der uebergebenen Sandbox-DB.
  - liefert deterministische Gruende wie `watch_config_table_missing` oder `schema_unknown`.

## Sicherheitsprinzip

- Keine Schema-Ratespiele: Spalten werden immer zur Laufzeit introspektiert.
- Kein Blind-Update auf produktive DB: fuer Devtools-Workflows wird eine Sandbox-DB-Kopie empfohlen.
- Keine PII-Ausgabe: Rueckgaben enthalten nur technische Statusdaten.
