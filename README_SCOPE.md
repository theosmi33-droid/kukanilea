# Scope: dashboard

## Ownership
- Tab slug: dashboard
- Branch: codex/dashboard
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/dashboard

## Allowed Paths
- app/templates/dashboard.html
- app/templates/components/system_status.html
- app/core/observer.py
- app/core/auto_evolution.py

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter dashboard --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
