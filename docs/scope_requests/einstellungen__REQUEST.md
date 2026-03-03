# Scope Request: einstellungen

## Context
Hard gate `check_domain_overlap.py` reports `DOMAIN_OVERLAP_DETECTED` for required Sovereign-11 files.

Date: 2026-03-02
Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/einstellungen`
Branch: `codex/einstellungen`

## Requested Scope Expansion
Please allow the following files/changes for this domain:

- `app/web.py` (Zero-CDN: local tailwind/htmx in HTML_BASE, White-Mode default, HTMX-Nav)
- `app/templates/layout.html` (Zero-CDN: local tailwind/htmx, White-Mode enforcement, theme toggle removal)
- `app/templates/partials/sidebar.html` (HTMX-Navigation for all sidebar items)
- `.gitignore` (Add .vscode/ to ensure clean worktree)

## Why
Sovereign-11 requirements mandate:
- **Zero-CDN:** All assets served locally.
- **White-Mode-only:** Enforced light-mode UI.
- **HTMX-Navigation:** SPA-like transitions.
- **Worktree Cleanliness:** Preventing IDE-specific settings leak.

Without modifying these core files, the `einstellungen` domain cannot comply with the Sovereign-11 architectural standards.
