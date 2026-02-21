# REPORT_SBOM

Date: 2026-02-21  
Status: BLOCKED

## Scope
- Supply-chain evidence for RC gate:
  - Dependency inventory (SBOM)
  - Vulnerability scan summary

## Generator

```bash
python scripts/generate_sbom.py --format cyclonedx --out output/sbom/sbom.cdx.json --with-pip-audit
python scripts/generate_sbom.py --format spdx --out output/sbom/sbom.spdx.json
```

## Current Status

- BLOCKED for RC decision until a fresh SBOM and scan report is attached to release evidence package.

## Evidence Section (to fill per release)

- SBOM path:
- SBOM format:
- Generation timestamp:
- Vulnerability summary:
- Exceptions (if any):
- Verdict: PASS / FAIL
