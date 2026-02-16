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

4. Optional strict:
```bash
python -m app.devtools.cli_ocr_test --tenant dev --doctor --strict --json
```

5. PR finalisieren und mergen.

## Acceptance Criteria

- Doctor liefert `ok=true` oder `reason=ok_with_warnings` (non-strict).
- Keine PII-Leaks (`pii_found_knowledge=false`, `pii_found_eventlog=false`).
- Exit-Code-Vertrag eingehalten (0/2/1).

## Rollback (nur Git, keine Runtime-Kommandos)

1. Revert-Merge Commit:
```bash
git checkout main
git pull --ff-only
git revert <merge_commit_sha>
git push origin main
```

2. Incident-Hinweis in PR/Runbook dokumentieren.
