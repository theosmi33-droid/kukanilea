# KUKANILEA Tab Ownership Rules

## Purpose
Prevent cross-domain coding and enforce deterministic ownership per tab.

## Rule Set
1. Domain isolation
- A tab project may edit only files in its allowlist.

2. Shared-core guard
- Any change touching these files requires explicit approval and a merge session:
  - `app/web.py`
  - `app/core/logic.py`
  - `app/__init__.py`
  - `app/db.py`

3. Overlap veto
- If two tab projects touch the same file, emit:
  - `DOMAIN_OVERLAP_DETECTED`
- Then stop implementation until a consolidation session is done.

4. API-first integration
- Cross-tab features must use existing service boundaries and tool registry; avoid direct ad-hoc cross-domain SQL.

5. Offline-first
- No new cloud dependencies without explicit product/security approval.

6. Evidence minimum before merge
- List changed files.
- Run relevant tests.
- Run overlap check script.

## Required command before commit
`python scripts/dev/check_domain_overlap.py --reiter <tab_slug> --files <changed_file_1> <changed_file_2> ...`

## Exit behavior
- If overlap or guard violation is detected, project returns NON-GO with file list and required owner approval.

## Registered tab slugs
- `dashboard`
- `upload`
- `emailpostfach`
- `messenger`
- `kalender`
- `aufgaben`
- `zeiterfassung`
- `projekte`
- `excel-docs-visualizer`
- `einstellungen`
- `floating-widget-chatbot`

## Parallel UI branch guard (Conflict Preventer)
- Canonical lane ownership and CI thresholds live in `.github/policy/ui_conflict_guardrails.json`.
- Merge sequencing for UI lanes lives in `docs/MERGE_ORDER_UI.md`.
- CI gate command: `python scripts/dev/ui_conflict_preventer.py --base-branch origin/main`.
- Hard requirement: each run executes at least `2100` scoped ownership checks (`owner_rules_checked`).
