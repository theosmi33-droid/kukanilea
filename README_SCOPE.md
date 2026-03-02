# README_SCOPE - Project 11: Floating Widget Chatbot

## Single Source of Truth
- /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/PRODUCT_DOMAINS_OVERVIEW.md

## Scope
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot`
- Expected branch: `codex/floating-widget-chatbot`
- Goal: Kontextbewusster globaler Assistent ueber alle Module mit Confirm-Gates und lokalem LLM-Fallback.

## Owned Paths (only)
- `floating widget template/partial in domain scope`
- `widget JS/CSS in domain scope`
- `chat skill orchestration layer in domain scope`

## Protected Cross-Domain Files (request required)
- `app/web.py`
- `app/db.py`
- `app/core/logic.py`
- `global layout/sidebar/auth/policy files`

## Mandatory Start Checklist
1. Read SSOT and this scope file.
2. Run overlap check before each edit:
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter floating-widget-chatbot --files <file> --json`
3. Sync shared state:
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py init`
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py read`

## Mandatory Writeback (after each meaningful step)
`python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py upsert-domain --domain floating-widget-chatbot --action "<action>" --commit <hash_or_local_only> --status <IN_PROGRESS|COMPLETED|BLOCKED> --actor <agent_name> --source <codex|gemini|vscode>`

## Start Prompt (copy/paste)
```text
You are Domain Owner for KUKANILEA: Floating Widget Chatbot.
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/floating-widget-chatbot
Branch: codex/floating-widget-chatbot
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
