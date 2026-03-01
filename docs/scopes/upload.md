# Scope: upload

## Ownership
- Tab slug: upload
- Branch: codex/upload
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/upload

## Allowed Paths
- app/core/upload_pipeline.py
- app/core/ocr_corrector.py
- app/core/rag_sync.py
- app/templates/review.html
- app/templates/dashboard.html (upload area only)

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter upload --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
