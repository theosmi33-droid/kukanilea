# Contributing

## PR Quality Guard (Hard Gate)

Alle Pull Requests müssen den `PR Quality Guard` bestehen:

```bash
bash scripts/dev/pr_quality_guard.sh --ci
```

### Gate-Regeln

- **MIN_SCOPE**: mindestens `7` geänderte Dateien **oder** `200` LOC Diff.
- **MIN_TESTS**: mindestens `6` Test-Delta (hinzugefügte/entfernte Test-LOC).
- **Evidence Report Pflicht**: Datei muss existieren unter
  `docs/reviews/codex/PR_QUALITY_GUARD_REPORT_20260305.md`.
- **Lane Overlap Check**: keine überlappenden Dateipfade mit anderen lokalen `codex/*`-Branches.

### Lokal prüfen

```bash
bash scripts/dev/pr_quality_guard.sh
```

Optional kann der Base-Branch explizit gesetzt werden:

```bash
bash scripts/dev/pr_quality_guard.sh --base-branch main
```
