# Scope Request: floating-widget-chatbot

## Context
Hard gate `check_domain_overlap.py` reports `DOMAIN_OVERLAP_DETECTED` for required Project 11 files.

Date: 2026-03-01
Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot`
Branch requested: `codex/floating-widget-chatbot`

## Requested Scope Expansion
Please allow the following files for this domain:

- `app/templates/layout.html` (global include + async bundle loader)
- `app/templates/partials/floating_chat.html` (new widget template)
- `app/static/js/chatbot.js` (new widget runtime)
- `app/static/css/components.css` (widget styles)
- `app/web.py` (route scope only: `/api/chat/compact`)
- `tests/test_chat_widget_compat.py` (compat update)
- `tests/test_floating_widget_chatbot.py` (new compact/confirm tests)
- `docs/user/widget_chatbot.md`
- `docs/admin/enable_widget.md`

## Why
Project 11 requirements mandate:
- global floating widget on every page,
- context-aware backend payload (`Current_Context`),
- confirm-gate before state-changing actions,
- compact endpoint and widget-specific persistence/history.

Without extending scope to `app/web.py` (`/api/chat/compact`) and new widget files, the mission cannot be completed without violating the hard gate.

## Minimal Injection Point (if strict layout-only policy)
If full scope is not approved, minimal viable hook still needed:
1. one include in layout: `{% include 'partials/floating_chat.html' %}`
2. one root hook div/section for the widget container
3. one JS bundle load: `/static/js/chatbot.js`
