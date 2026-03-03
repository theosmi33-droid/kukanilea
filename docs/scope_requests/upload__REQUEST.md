# Scope Request: upload

## Context
Hard gate `check_domain_overlap.py` reports `DOMAIN_OVERLAP_DETECTED` for required Sovereign-11 files.

Date: 2026-03-02
Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/upload`
Branch: `codex/upload`

## Requested Scope Expansion
Please allow the following files/changes for this domain:

- `app/web.py` (Zero-CDN: local tailwind/htmx in HTML_BASE, White-Mode default, HTMX-Nav)
- `app/templates/layout.html` (Zero-CDN: local tailwind/htmx, White-Mode enforcement, theme toggle removal)
- `app/templates/partials/sidebar.html` (HTMX-Navigation for all sidebar items)
- `.gitignore` (Add .vscode/ to ensure clean worktree)

## Why
Sovereign-11 requirements mandate:
- **Zero-CDN:** No external Tailwind or HTMX loads; all assets served locally to comply with CSP and offline-first policy.
- **White-Mode-only:** Removal of dark-theme toggles and enforcement of a consistent light-mode UI.
- **HTMX-Navigation:** Faster, more dynamic navigation using HTMX `hx-get`, `hx-target`, and `hx-push-url`.
- **Worktree Cleanliness:** Preventing IDE-specific settings from being tracked across worktrees.

Without modifying these core files, the `upload` domain cannot comply with the Sovereign-11 architectural standards while providing its required UI.

## Minimal Injection Point
If full scope for `app/web.py` is restricted, we still need:
1. One local Tailwind/HTMX load in `layout.html`.
2. One light-mode enforcement script in `layout.html`.
3. One HTMX navigation update in `sidebar.html`.
