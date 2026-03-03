# Scope Request: zeiterfassung

## Context
Domain `zeiterfassung` is blocked by Shared-Core ownership while critical UI/logic still live in core files.

Date: 2026-03-03
Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/zeiterfassung`
Branch: `codex/zeiterfassung`

## Requested Scope Expansion
Please allow controlled integration changes in the following Shared-Core files:

- `app/web.py`
  - Extract `/time` rendering away from `HTML_TIME` inline script blocks.
  - Align `/time` with HTMX shell behavior (partial-friendly responses).
  - Remove hardcoded dark-oriented utility classes in time-tracking markup.
- `app/core/logic.py`
  - Keep existing behavior but create extension points for domain-local module delegation.
  - Preserve current API compatibility (`time_entry_start`, `time_entry_stop`) during migration.

## Why
Current domain findings show:

- Shared-Core coupling prevents domain-owned evolution (`CROSS_DOMAIN_WARNING`).
- Time UI in core violates Sovereign-11 consistency goals:
  - White-mode only (no dark styling regressions)
  - HTMX-first interaction model
- Without this scope request, zeiterfassung cannot be hardened without violating ownership rules.

## Guardrails

- No destructive DB changes in this request.
- No route removals without backward-compatible aliases.
- All changes must pass:
  - `pytest -q`
  - `python scripts/dev/check_domain_overlap.py --reiter zeiterfassung --files <changed_files>`

## Target Outcome

1. Time tracking UI no longer depends on a large inline block in `app/web.py`.
2. Shared-Core keeps only stable wiring; domain owns most presentation logic.
3. White-mode/HTMX compliance is improved without breaking existing `/time` behavior.
