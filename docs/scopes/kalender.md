# Scope: kalender

## Ownership
- Tab slug: kalender
- Branch: codex/kalender
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/kalender

## Allowed Paths
- app/knowledge/ics_source.py
- app/knowledge/core.py
- app/templates/generic_tool.html (until dedicated calendar template exists)

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter kalender --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
