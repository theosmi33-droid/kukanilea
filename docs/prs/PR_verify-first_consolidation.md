## Title
chore(security+ops): verify-first consolidation, hardening gates, and phased TEXT-ID migration plan

## Working directory (local)
Codex arbeitet lokal in:
`/Users/gensuminguyen/Tophandwerk/kukanilea-git/`

## Why
Dieses PR schliesst Konsistenz- und Security-Luecken mit einem **verify-first** Ansatz:
- keine unueberpruefbaren Behauptungen (keine "pushed/commit XYZ" ohne `git log` / Remote-Check)
- harte Security-/Compliance-Gates
- risikoarme Migration in Phasen statt Big-Bang

## Scope
### A) Entry-Point + Python-Floor
- Entry-Point auf `kukanilea_app.py` konsolidiert (nur dort, wo fachlich korrekt).
- Python-Version auf 3.11/3.12 konsistent gemacht (Runtime + Doku-Pfade).

**Touched files (pruefbar via `git diff --name-only`):**
- `scripts/build_mac.sh`
- `scripts/gen_launchd_plist.sh`
- `scripts/gen_systemd_unit.sh`
- `scripts/gen_windows_service.ps1`
- `pyproject.toml`
- `.python-version`

### B) Core-Freeze Enforcement
- Pre-commit/CI-Policy: Dependency-Aenderungen nur mit ADR + Review-Gate.
- CONTRIBUTING + PR-Template erweitert um Security-/Tenant-/READ_ONLY-Checks.

**Touched files (Beispiele):**
- `.pre-commit-config.yaml`
- `scripts/check_core_freeze.py`
- `docs/PR_REVIEW_CHECKLIST.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

### C) Security Hardening
- Timing-resistente Vergleiche fuer Tokens/Secrets (`hmac.compare_digest`).
- IMAP nur TLS: `IMAP4_SSL` + `ssl_context=ssl.create_default_context()` (fail-closed, keine unsicheren Fallbacks).
- Keine Klartext-Secrets in DB: sichere Speicherung erzwingen, ansonsten Fehler statt "unsicher weiter".
- OCR/Mail-Persistenz nur redigiert (keine PII im Persist-Layer).
- Statischer Security-Scan als Gate (u.a. risky patterns wie `shell=True`, fehlende Timeouts).

Hinweis: `compare_digest` wird explizit als timing-resistenter Vergleich dokumentiert.  
Hinweis: `IMAP4_SSL` kann `ssl_context` nutzen; `create_default_context` ist der Standardweg.  
Hinweis: `subprocess.run` unterstuetzt `timeout`; `shell` sollte i.d.R. vermieden werden.

### D) Doku-Konsolidierung
- `ONBOARDING.md` als zentrale Quelle (Single Source of Truth).
- Ergaenzt: `WEEKLY_TEMPLATE.md`, `GLOSSARY.md`, `TEAM_ROLES.md`, `SECURITY.md`.
- README/ARCHITECTURE/CONSTITUTION/ROADMAP/PROJECT_STATUS konsistent aktualisiert.

### E) TEXT-ID Migration (phasenweise)
- Kein globaler PK-Umbau in diesem PR.
- Schema-Audit-Tool (Human + JSON + optional fail mode).
- ADR + Runbook fuer phased migration inkl. SQLite Table-Rebuild-Strategie (Drop/PK-Change i.d.R. via table rebuild).

## How to verify (local)
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

## Evidence (paste outputs)
- `pytest -q`: `326 passed, 1 skipped, 24 warnings in 10.57s`
- `security_scan`: `{\"ok\": true, \"count\": 0, \"findings\": []}`
- `triage --ci`: `{\"json_report\": \"triage_report.json\", \"exit_code\": 0}`
- `schema_audit`: `core ok=false findings=30; auth ok=false findings=4` (legacy INTEGER PK inventory as planned)

## Out of scope
- Kein globaler PK-Umbau aller Legacy-Tabellen in einem Schritt.
- Keine neuen Dependencies.
- Kein History-Rewrite von `main`.

## Risks
- Legacy-Tabellen mit INTEGER-PKs bleiben vorerst bestehen (bewusst zur Risikominimierung).
- Vollstaendige TEXT-ID-Cutover erfolgen in Folge-PRs pro Tabelle (mit Backfill + Kompatibilitaetsphase).

## Rollback
- PR/Commit-basiert reversibel.
- Keine "silent" Datenmigrationen in diesem PR; Table-Rebuild-Migrationen sind Folge-PRs.
