# Contributing

## PR Quality Guard (Hard Gate)

Alle Pull Requests müssen den `PR Quality Guard` bestehen:

```bash
bash scripts/dev/pr_quality_guard.sh --ci
```

### Gate-Regeln

- **MAX_SCOPE**: höchstens `12` geänderte Dateien **und** höchstens `350` LOC Diff.
- **Focused Scope**: höchstens `3` Änderungsbereiche (Top-Level + Subpfad), um fachfremde Nebenänderungen zu verhindern.
- **MIN_TESTS**: mindestens `6` Test-Delta (hinzugefügte/entfernte Test-LOC).
- **Evidence Report Pflicht**: Datei muss existieren unter
  `docs/reviews/codex/PR_QUALITY_GUARD_REPORT_20260305.md`.
- **Main-First Base**: Guard verifiziert `origin/main` als Basis (in CI verpflichtend).
- **Shared-Core Hotspot Block**: Änderungen an `app/web.py`, `app/core/logic.py`, `app/__init__.py`, `app/db.py`, `app/templates/layout.html` müssen als separater fokussierter PR erfolgen.

### Lokal prüfen

```bash
bash scripts/dev/pr_quality_guard.sh
```

Optional kann der Base-Branch explizit gesetzt werden:

```bash
bash scripts/dev/pr_quality_guard.sh --base-branch main
```
