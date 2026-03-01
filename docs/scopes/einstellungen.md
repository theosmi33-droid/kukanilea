# Scope: einstellungen

## Ownership
- Tab slug: einstellungen
- Branch: codex/einstellungen
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/einstellungen

## Allowed Paths
- app/core/tenant_registry.py
- app/core/mesh_network.py
- app/license.py
- app/routes/admin_tenants.py
- app/templates/settings.html

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter einstellungen --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
