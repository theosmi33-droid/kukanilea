# OCR v0 Merge Checklist

## Zweck

Schrittfolge fuer sicheren Merge von OCR v0 mit reproduzierbaren Smoke-Checks und klarer Rollback-Option.

## Vorbedingungen

- Branch `main` ist aktuell.
- OCR-Devtools inkl. Doctor sind verfuegbar.
- Keine produktiven Kundendaten im Testtenant.

## Merge-Ablauf (Docs-only Anleitung)

1. Rebase des OCR-v0 Branches:
```bash
git fetch origin
git checkout codex/feat/autonomy-ocr-v0
git rebase origin/main
```

2. Quality Gates lokal:
```bash
python -m compileall -q .
ruff check . --fix
ruff format .
pytest -q
python -m app.devtools.triage --ci --fail-on-warnings \
  --ignore-warning-regex "(?i)(swig|deprecation|userwarning|resourcewarning|warning:)"
```

3. Doctor-Check im Sandbox-Mode:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --json
```

4. Deterministischer OCR-Smoke mit Sandbox-Policy + Direct-Submit:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --enable-policy-in-sandbox --direct-submit-in-sandbox --json --timeout 30
```

5. Optional strict:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --strict --json
```

6. PR finalisieren und mergen.

## Acceptance Criteria

- Doctor liefert `ok=true` oder `reason=ok_with_warnings` (non-strict).
- Keine PII-Leaks (`pii_found_knowledge=false`, `pii_found_eventlog=false`).
- Exit-Code-Vertrag eingehalten (0/2/1).

## Known Failure Matrix

| reason | Bedeutung | Felder/Checks |
|---|---|---|
| `policy_denied` | OCR policy fuer Tenant nicht aktiv | `policy_enabled_base`, `policy_enabled_effective` |
| `tessdata_missing` | Tessdata nicht aufloesbar | `tessdata_candidates`, `probe_reason` |
| `language_missing` | Gewaehlte Sprache fehlt | `tesseract_langs`, `lang_used`, `probe_next_actions` |
| `job_not_found` | kein OCR-Job erzeugt | `scanner_discovered_files`, `inbox_dir_used`, `direct_submit_used` |
| `read_only` | Mutationen gesperrt | `read_only=true` |
| `config_file_missing` | Tesseract config loading Fehler | `tesseract_stderr_tail`, `probe_reason` |

## Rollback (nur Git, keine Runtime-Kommandos)

1. Revert-Merge Commit:
```bash
git checkout main
git pull --ff-only
git revert <merge_commit_sha>
git push origin main
```

2. Incident-Hinweis in PR/Runbook dokumentieren.
