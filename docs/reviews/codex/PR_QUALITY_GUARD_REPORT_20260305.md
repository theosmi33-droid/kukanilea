# PR Quality Guard Report — 2026-03-05

## Ziel
Absicherung gegen zu kleine / nicht belegte PRs durch einen verbindlichen Guard in Dev-Workflow und CI.

## Eingeführte Gates
1. **MIN_SCOPE**: `>= 7` Dateien oder `>= 200` LOC.
2. **MIN_TESTS**: `>= 6` Test-Delta (Test-LOC).
3. **Evidence Required**: dieses Dokument muss in der PR vorhanden sein.
4. **Lane Overlap Check**: Fail bei Dateiüberlappung mit anderen lokalen `codex/*`-Branches.

## CI-Gate
- Command: `bash scripts/dev/pr_quality_guard.sh --ci`
- Workflow: `.github/workflows/ci.yml` (PR-Job `pr-quality-guard`)

## Simulationen
- Thin PR: **FAIL**
- Solid PR: **PASS**
- Overlap PR: **FAIL**
