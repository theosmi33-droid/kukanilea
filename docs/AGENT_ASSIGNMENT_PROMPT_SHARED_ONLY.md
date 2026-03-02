# KUKANILEA Agent Assignment Prompt (Shared DB + Locking)

Use this prompt for every external agent (Codex in VS Code, Gemini CLI, other copilots).

```text
ROLE
You are a domain-specific KUKANILEA engineer.
You must follow domain isolation and synchronize through shared SQLite only.

DOMAIN SCOPE
- Domain: <DOMAIN_NAME>
- Allowed paths: <PATH_LIST>
- Forbidden core paths without explicit approval:
  app/web.py, app/db.py, app/__init__.py, app/core/logic.py

MANDATORY STATE SOURCE (ONLY)
- Shared DB: /Users/gensuminguyen/Kukanilea/data/agent_orchestra_shared.db
- Before any change:
  1) python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py init
  2) python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py read

SESSION + LOCK (required)
- Start session:
  python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py start-session \
    --actor <AGENT_NAME> \
    --source <codex|gemini|vscode> \
    --domain <DOMAIN_NAME> \
    --branch <BRANCH_NAME> \
    --worktree <WORKTREE_PATH> \
    --note "start"
- Lock domain:
  python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py lock-domain \
    --domain <DOMAIN_NAME> \
    --session-id <SESSION_ID> \
    --actor <AGENT_NAME> \
    --source <codex|gemini|vscode> \
    --minutes 120 \
    --reason "active_work"
- If lock fails (`ok=false`), stop and report conflict.

MANDATORY WRITEBACK
After each meaningful action or commit:
python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py upsert-domain \
  --domain <DOMAIN_NAME> \
  --action "<ACTION_SUMMARY>" \
  --commit <COMMIT_HASH_OR_local_only> \
  --status <IN_PROGRESS|COMPLETED|BLOCKED> \
  --actor <AGENT_NAME> \
  --source <codex|gemini|vscode>

Heartbeat every 10-15 minutes:
python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py heartbeat \
  --session-id <SESSION_ID> \
  --actor <AGENT_NAME> \
  --source <codex|gemini|vscode> \
  --status ACTIVE \
  --note "<CURRENT_STEP>"

SESSION CLOSE (required)
python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py unlock-domain \
  --domain <DOMAIN_NAME> \
  --session-id <SESSION_ID> \
  --actor <AGENT_NAME> \
  --source <codex|gemini|vscode>

python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py end-session \
  --session-id <SESSION_ID> \
  --actor <AGENT_NAME> \
  --source <codex|gemini|vscode> \
  --status COMPLETED \
  --note "handoff done"

GITHUB HANDOFF
If creating PRs or major architecture decisions:
1) python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py snapshot --output /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/shared_memory_snapshot.json
2) Include docs/shared_memory_snapshot.json in branch/PR evidence.

QUALITY GATE
- Run overlap check before commit.
- Run pytest for touched scope.
- No destructive commands.
- No cloud storage for shared context.
```

