# Scope: messenger

## Ownership
- Tab slug: messenger
- Branch: codex/messenger
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/messenger

## Allowed Paths
- app/agents/orchestrator.py
- app/agents/planner.py
- app/agents/memory_store.py
- app/templates/messenger.html

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter messenger --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
