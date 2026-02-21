# REPORT_PROVENANCE

Date: 2026-02-21  
Status: BLOCKED

## Scope
- Provenance and integrity evidence for release artifacts.

## Commands

```bash
python scripts/generate_build_manifest.py --input-dir dist --out output/build/manifest.json
python scripts/generate_provenance.py --artifacts-dir dist --out output/provenance/provenance.json
```

## Current Status

- BLOCKED for RC decision until release-specific artifacts and provenance outputs are attached.

## Evidence Section (per release)

- Build manifest path:
- Provenance path:
- Artifact digest verification result:
- Optional attestation verification result:
- Verdict: PASS / FAIL
