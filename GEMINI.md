# KUKANILEA Agent Runtime Rule (verbindlich)

Du arbeitest im KUKANILEA Multi-Worktree-System.
Vor jeder Aktion MUSST du den Shared-Status aus SQLite lesen.

## Shared DB
Pfad: /Users/gensuminguyen/Kukanilea/data/agent_orchestra_shared.db

## PRE-FLIGHT (immer zuerst)
1. SELECT key, value, updated_at FROM global_context ORDER BY updated_at DESC;
2. SELECT id, directive, priority, active, updated_at FROM shared_directives WHERE active=1 ORDER BY priority DESC, updated_at DESC;
3. SELECT domain, status, last_action, last_commit, updated_at FROM domain_sync ORDER BY updated_at DESC;

## DOMAIN-RULE
- Nur im eigenen Worktree arbeiten.
- Shared-Core-Dateien nur via Scope-Request:
  app/web.py, app/db.py, app/core/logic.py, app/templates/layout.html

## POST-FLIGHT (nach Erfolg)
INSERT INTO domain_sync(domain,status,last_action,last_commit,updated_at)
VALUES('<DOMAIN>','COMPLETED','<AKTION>','<COMMIT_HASH>',strftime('%Y-%m-%dT%H:%M:%fZ','now'))
ON CONFLICT(domain) DO UPDATE SET
status=excluded.status,
last_action=excluded.last_action,
last_commit=excluded.last_commit,
updated_at=excluded.updated_at;
