# README_SCOPE - Project 9: Visualizer (Excel/Docs)

## Single Source of Truth
- /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/PRODUCT_DOMAINS_OVERVIEW.md

## Scope
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer`
- Expected branch: `codex/excel-docs-visualizer`
- Goal: Dokumente rendern, zusammenfassen, visualisieren und projektfaehig speichern.

## Owned Paths (only)
- `app/templates/visualizer.html`
- `visualizer rendering/adapters in domain scope`
- `export helpers in domain scope`

## Protected Cross-Domain Files (request required)
- `app/web.py`
- `app/db.py`
- `app/core/logic.py`
- `global layout/sidebar/auth/policy files`

## Mandatory Start Checklist
1. Read SSOT and this scope file.
2. Run overlap check before each edit:
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter excel-docs-visualizer --files <file> --json`
3. Sync shared state:
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py init`
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py read`

## Mandatory Writeback (after each meaningful step)
`python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py upsert-domain --domain excel-docs-visualizer --action "<action>" --commit <hash_or_local_only> --status <IN_PROGRESS|COMPLETED|BLOCKED> --actor <agent_name> --source <codex|gemini|vscode>`

## Start Prompt (copy/paste)
```text
You are Domain Owner for KUKANILEA: Visualizer (Excel/Docs).
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/excel-docs-visualizer
Branch: codex/excel-docs-visualizer
Work only in owned files. If a change needs app/web.py, app/db.py, app/core/logic.py, or global shell files: emit CROSS_DOMAIN_WARNING and stop for scope request.
Before any edit, run overlap check and shared memory read. After each meaningful change, write domain status to shared memory.
Keep changes minimal, testable, and offline-first. No destructive git operations.
```

## Definition of Done (Domain)
- Scope respected, no unauthorized cross-domain edits.
- Relevant tests for touched area pass.
- Offline degrade behavior is explicit and user-visible.
- Audit and confirm-gate behavior preserved for risky actions.
- Shared memory updated with final status.
