# REPORT_RC_DISTRIBUTION_MACOS

Date: 2026-02-21  
Status: BLOCKED

## Blocker

- Missing Apple Developer ID signing assets and/or notarization credentials.

## Prerequisites Reference

- `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/docs/RC_SIGNING_PREREQUISITES.md`
- `/Users/gensuminguyen/Tophandwerk/kukanilea-bench/docs/RC_NOTARIZATION_PIPELINE.md`

## Commands To Run Once Unblocked

```bash
spctl --assess --type open --verbose <path_to_app_or_dmg>
xcrun stapler validate <path_to_app_or_dmg>
```

## PASS Criteria

- `spctl` returns accepted policy assessment.
- `stapler validate` confirms stapled ticket validation success.

## Evidence Section (to fill when available)

- Artifact path:
- `spctl` output:
- `stapler validate` output:
- Verdict: PASS / FAIL
