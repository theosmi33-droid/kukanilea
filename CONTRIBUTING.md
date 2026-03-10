# Contributing

## PR Quality Guard (Hard Gate)

Alle Pull Requests müssen den `PR Quality Guard` bestehen:

```bash
bash scripts/dev/pr_quality_guard.sh --ci
```

### Gate-Regeln

- **MIN_SCOPE**: mindestens `2` geänderte Dateien **oder** `80` LOC Diff.
- **MIN_TESTS**: mindestens `6` Test-Delta (hinzugefügte/entfernte Test-LOC).
- **Evidence Report Pflicht**: Datei muss existieren unter
  `docs/reviews/codex/PR_QUALITY_GUARD_REPORT_20260305.md`.
- **Lane Overlap Check**: keine überlappenden Dateipfade mit anderen lokalen `codex/*`-Branches.
- **Main-Only Base**: jeder PR muss auf `main` basieren und gegen `main` geöffnet werden.
- **Main-Only Freshness**: wenn `origin/main` lokal verfügbar ist, darf der Branch nicht hinter `origin/main` liegen (`behind=0`).
- **Kein Branch-Stacking**: aktueller Branch darf keine Commits eines anderen lokalen `codex/*`-Branches enthalten.

### Lokal prüfen

```bash
bash scripts/dev/pr_quality_guard.sh
```

Optional kann der Base-Branch explizit gesetzt werden:

```bash
bash scripts/dev/pr_quality_guard.sh --base-branch main
```
