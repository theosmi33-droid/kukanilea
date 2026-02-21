# EVIDENCE_PACK_SCHEMA

Date: 2026-02-21

## Purpose
Standardize release evidence collection so Go/No-Go decisions are auditable and reproducible.

## Directory Schema

```text
evidence/<version>/
  security/
  e2e/
  perf/
  distribution/
  update/
  sbom/
  provenance/
  compliance/
```

## Expected Content by Section

- `security/`: security reports, vulnerability summaries, key logs.
- `e2e/`: flow summaries, failing screenshots/traces references.
- `perf/`: latency CSV/JSON and endurance summary.
- `distribution/`: signing/notarization/verification outputs.
- `update/`: update/rollback proof reports.
- `sbom/`: CycloneDX/SPDX outputs and vulnerability scan metadata.
- `provenance/`: build manifest and provenance statement.
- `compliance/`: release gates snapshot and compliance checklists.

## Tooling

```bash
python scripts/prepare_evidence_pack.py --version <version> --copy-defaults
```

## Rules

- Never store raw secrets in evidence pack.
- Treat screenshots/logs as potentially sensitive; apply retention policy.
- Missing mandatory evidence keeps gate in `BLOCKED`/`FAIL`.
