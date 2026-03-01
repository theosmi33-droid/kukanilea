# Scope: excel-docs-visualizer

## Ownership
- Tab slug: excel-docs-visualizer
- Branch: codex/excel-docs-visualizer
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer

## Allowed Paths
- app/templates/visualizer.html
- app/static/js/

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter excel-docs-visualizer --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
