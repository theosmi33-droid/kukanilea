# Codex Prompt (Verify-First, Local)

Du bist Codex und arbeitest lokal im Repo:
`/Users/gensuminguyen/Tophandwerk/kukanilea-git/`

## Non-negotiable (verify-first)
1. Behaupte nichts, was du nicht lokal verifizieren kannst.
- Keine Aussagen wie "pushed", "Commit abc123", "Branch existiert" ohne `git`-Output.
- Wenn Remote nicht verfuegbar ist: explizit sagen und lokale Nachweise geben.

2. Arbeite ausschliesslich innerhalb des Repo-Pfads.

3. Jede Aenderung muss durch `git diff`/`git status` sichtbar sein und durch Gates verifiziert werden.

4. Security-Regeln:
- Timing-safe Vergleiche: `hmac.compare_digest` fuer Secrets/Tokens.
- IMAP: nur `IMAP4_SSL` + `ssl_context=ssl.create_default_context()`; kein unsicherer Fallback.
- Subprocess: kein `shell=True` (ausser zwingend + ADR), immer `timeout`.
- OCR/Mail Persistenz: nur redigierter Text (keine PII).

5. TEXT-ID Migration:
- Kein globaler Big-Bang.
- Nur Audit + Plan + Phase-1 Kandidaten.
- SQLite PK-Aenderungen i.d.R. via table-rebuild (create/copy/rename).

## Tasks
A) Entry-Point auf `kukanilea_app.py` pruefen und konsolidieren.
B) Python-Floor 3.11/3.12 konsistent machen.
C) Core-Freeze Gates (`check_core_freeze.py`, pre-commit, PR checklist/template).
D) Security Hardening (compare_digest, IMAP SSL, no plaintext secrets, OCR redaction, security scan).
E) Doku-Konsolidierung (`ONBOARDING.md`, Templates, Rollen, Security).
F) TEXT-ID phased migration (`schema_audit`, ADR, runbook, tests).

## Verification Gates
```bash
cd /Users/gensuminguyen/Tophandwerk/kukanilea-git/
python -m compileall -q .
ruff check .
ruff format . --check
pytest -q
python -m app.devtools.security_scan
python -m app.devtools.triage --ci --fail-on-warnings
python -m app.devtools.schema_audit
```

## Deliverables
1. `git status` und `git diff --stat`
2. Vollstaendige Liste geaenderter Dateien
3. Gate-Ausgaben (kurz, beweiskraeftig)
4. PR-Beschreibung unter `docs/prs/PR_verify-first_consolidation.md`
5. Keine Aussagen ueber Push/Remote/Commit ohne Beleg
