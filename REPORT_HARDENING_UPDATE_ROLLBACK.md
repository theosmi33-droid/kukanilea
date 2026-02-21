# REPORT_HARDENING_UPDATE_ROLLBACK

Date: 2026-02-21  
Worktree: `/Users/gensuminguyen/Tophandwerk/kukanilea-bench`  
Branch: `codex/bench-and-stability`

## Scope
- Automated proof for:
  - Signed update manifest verification
  - Rollback behavior (success path + missing-backup guard)
- Manual installer rollback remains a release-captain checklist item.

## Pre-run git status
Command:
```bash
git status --porcelain=v1
```

Output:
```text
 M tests/test_update_mechanism.py
?? output/
```

## Commands
```bash
pytest -q tests/test_update_signing.py tests/test_update_mechanism.py
```

## Result Summary

| Gate Item | Expected | Actual | Status |
|---|---|---|---|
| Signed manifest accepted | valid signature marks update as installable | pass (`test_check_for_installable_update_with_signed_manifest`) | PASS |
| Bad signature rejected | invalid signature blocks installable update | pass (`test_check_for_installable_update_rejects_bad_signature`) | PASS |
| Manifest fetch fallback | unsigned fallback allowed only when `signing_required=False` | pass (`test_check_for_installable_update_manifest_fetch_fallback`) | PASS |
| Manifest required mode | fetch failure blocks update when signatures required | pass (`test_check_for_installable_update_manifest_fetch_required`) | PASS |
| Rollback success | restore previous build from backup dir | pass (`test_rollback_restores_previous_build`) | PASS |
| Rollback guard | missing backup returns deterministic error | pass (`test_rollback_requires_existing_backup`) | PASS |

## Evidence
- Test command output: `8 passed in 0.16s`
- Updated test file: `tests/test_update_mechanism.py`

## Remaining Manual Evidence (Release Gate)
- End-to-end installer rollback (real packaged app on target OS) is not automated here and must be captured in release evidence.
