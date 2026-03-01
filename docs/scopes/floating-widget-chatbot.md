# Scope: floating-widget-chatbot

## Ownership
- Tab slug: floating-widget-chatbot
- Branch: codex/floating-widget-chatbot
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot

## Allowed Paths
- app/templates/layout.html
- app/templates/partials/chat_widget.html
- app/static/js/chat_widget.js
- app/static/css/chat_widget.css

## Shared-Core Guard (hard stop)
- app/web.py
- app/core/logic.py
- app/__init__.py
- app/db.py

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Required Checks Before Commit
1. Overlap check
   python3 /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter floating-widget-chatbot --files <changed_file_1> <changed_file_2> ...
2. Baseline tests
   pytest -q
