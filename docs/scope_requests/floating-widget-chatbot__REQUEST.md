# Scope Request: floating-widget-chatbot

## Context
Domain `floating-widget-chatbot` requires Shared-Core updates to decouple chat widget code from shell layout.

Date: 2026-03-03  
Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot`  
Branch: `codex/floating-widget-chatbot`

## Requested Scope Expansion
Please allow controlled integration changes in the following Shared-Core files:

- `app/templates/layout.html`
  - Replace inline chat widget HTML/JS/CSS blocks with:
    - `app/templates/partials/chat_widget.html`
    - `app/static/js/chat_widget.js`
    - `app/static/css/chat_widget.css`
  - Keep shell behavior intact (sidebar, HTMX frame, white-mode bootstrapping).
- `app/web.py` (only if needed for compatibility)
  - Keep `/api/chat` contract stable while enabling partial/widget-first rendering hooks.
- `tests/test_chat_widget_compat.py`
  - Update assertions to validate the new partial/static-based integration contract.

## Why
Current domain findings show:

- Chat widget is functionally correct but tightly embedded in shared layout.
- This creates Shared-Core bloat and slows maintenance.
- A clean separation needs layout touchpoints that domain ownership alone cannot change.

## Guardrails

- No removal of `/api/chat` compatibility (`data.text || data.response` behavior stays valid).
- Keep Zero-CDN and White-Mode-only guarantees.
- Preserve HTMX shell conventions.
- Validate with:
  - `pytest -q tests/test_chat_widget_compat.py`
  - `python scripts/dev/check_domain_overlap.py --reiter floating-widget-chatbot --files <changed_files>`

## Target Outcome

1. Chat widget is maintainable via partial + static assets.
2. Shared layout remains minimal and shell-focused.
3. Existing chat API behavior and UI contract remain backward compatible.
