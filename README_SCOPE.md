# README_SCOPE - Project 4: Messenger

## Ownership
- Tab slug: dashboard
- Branch: codex/dashboard
- Worktree: /Users/gensuminguyen/Kukanilea/worktrees/dashboard

## Scope
- Worktree: `/Users/gensuminguyen/Kukanilea/worktrees/messenger`
- Expected branch: `codex/messenger`
- Goal: Zentrale Kommunikationsdrehscheibe mit internen/externalen Kanaelen und lokaler Persistenz.

## Owned Paths (only)
- `app/templates/messenger.html`
- `messenger connector/services in domain scope`
- `internal chat domain files`

If a change touches shared core: emit CROSS_DOMAIN_WARNING and stop implementation.

## Mandatory Start Checklist
1. Read SSOT and this scope file.
2. Run overlap check before each edit:
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py --reiter messenger --files <file> --json`
3. Sync shared state:
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py init`
   `python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py read`

## Mandatory Writeback (after each meaningful step)
`python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py upsert-domain --domain messenger --action "<action>" --commit <hash_or_local_only> --status <IN_PROGRESS|COMPLETED|BLOCKED> --actor <agent_name> --source <codex|gemini|vscode>`

## Start Prompt (copy/paste)
```text
You are Domain Owner for KUKANILEA: Messenger.
Worktree: /Users/gensuminguyen/Kukanilea/worktrees/messenger
Branch: codex/messenger
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
