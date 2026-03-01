# Scope: zeiterfassung

## Ownership
- Tab slug: zeiterfassung
- Branch: codex/zeiterfassung
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung

## Allowed Paths
- app/templates/generic_tool.html
- app/modules/projects/logic.py (project linkage only)

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter zeiterfassung --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
