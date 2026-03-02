# KUKANILEA Anweisungsschreiben: Gemeinsame KI-Datenbank (Fleet 11)

## Zweck
Alle Agenten (`Codex`, `Gemini CLI`, `VS Code`) arbeiten auf **demselben Stand** über eine zentrale SQLite-Datenbank:

- DB: `/Users/gensuminguyen/Kukanilea/data/agent_orchestra_shared.db`
- CLI: `/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py`

## Aktueller Befund
Die Datenbank existiert bereits und wurde erweitert um:
- `global_context`
- `domain_sync`
- `shared_directives`
- `sync_events`
- `agent_sessions` (neu)
- `domain_locks` (neu)

Damit sind jetzt Session-Tracking und Domain-Locks aktiv, um Überschneidungen zu verhindern.

## Einmalig ausführen (Fleet Commander)
```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
python scripts/shared_memory.py init
python scripts/shared_memory.py seed-domains \
  --domains dashboard,upload,emailpostfach,messenger,kalender,aufgaben,zeiterfassung,projekte,excel-docs-visualizer,einstellungen,floating-widget-chatbot \
  --actor fleet_commander \
  --source codex \
  --status PENDING
python scripts/shared_memory.py set-context --key sovereign_11_mode --value "ACTIVE" --actor fleet_commander --source codex
python scripts/shared_memory.py set-context --key sync_protocol --value "sessions+locks+domain_sync" --actor fleet_commander --source codex
```

## Verbindlicher Arbeitsablauf für ALLE Agenten

### 1) Preflight (Pflicht)
```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
python scripts/shared_memory.py init
python scripts/shared_memory.py read
```

### 2) Session starten
Beispiel (Domain `dashboard`):
```bash
python scripts/shared_memory.py start-session \
  --actor codex_dashboard \
  --source codex \
  --domain dashboard \
  --branch codex/dashboard \
  --worktree /Users/gensuminguyen/Kukanilea/worktrees/dashboard \
  --note "start implementation"
```

### 3) Domain locken (Pflicht vor Code-Änderung)
```bash
python scripts/shared_memory.py lock-domain \
  --domain dashboard \
  --session-id <SESSION_ID_AUS_START_SESSION> \
  --actor codex_dashboard \
  --source codex \
  --minutes 120 \
  --reason "feature work"
```

Wenn `ok=false`, **sofort stoppen** (Domain ist durch anderen Agenten gelockt).

### 4) Während der Arbeit (alle 10–15 Minuten)
```bash
python scripts/shared_memory.py heartbeat \
  --session-id <SESSION_ID> \
  --actor codex_dashboard \
  --source codex \
  --status ACTIVE \
  --note "implementing widget endpoint"
```

### 5) Nach jedem sinnvollen Schritt / Commit
```bash
python scripts/shared_memory.py upsert-domain \
  --domain dashboard \
  --action "implemented widget endpoint + tests" \
  --commit <COMMIT_HASH_ODER_local_only> \
  --status IN_PROGRESS \
  --actor codex_dashboard \
  --source codex
```

### 6) Abschluss (unlock + session end)
```bash
python scripts/shared_memory.py upsert-domain \
  --domain dashboard \
  --action "feature completed" \
  --commit <COMMIT_HASH_ODER_local_only> \
  --status COMPLETED \
  --actor codex_dashboard \
  --source codex

python scripts/shared_memory.py unlock-domain \
  --domain dashboard \
  --session-id <SESSION_ID> \
  --actor codex_dashboard \
  --source codex

python scripts/shared_memory.py end-session \
  --session-id <SESSION_ID> \
  --actor codex_dashboard \
  --source codex \
  --status COMPLETED \
  --note "handoff done"
```

## Copy/Paste für die 3 Clients

### A) Codex (Terminal)
- `--source codex`
- Actor-Schema: `codex_<domain>`

### B) Gemini CLI
- `--source gemini`
- Actor-Schema: `gemini_<domain>`

### C) VS Code (integriertes Terminal)
- `--source vscode`
- Actor-Schema: `vscode_<domain>`

Die Kommandos bleiben identisch, nur `--source` und `--actor` ändern.

## Konflikt-Protokoll (verbindlich)
1. Lock schlägt fehl (`ok=false`) → **keine** Codeänderung beginnen.
2. `python scripts/shared_memory.py read` ausführen und blockierende Session prüfen.
3. Wenn Lock stale wirkt (Heartbeat alt): Fleet Commander entscheidet über manuelles Unlock.
4. Erst danach neuer Lock-Versuch.

## Tägliche Team-Routine
1. 09:00: `read` ausführen, aktive Locks/Session prüfen.
2. Vor Start jeder Domäne: Session + Lock.
3. Während Arbeit: Heartbeat + Domain-Status.
4. Vor Feierabend: `COMPLETED/BLOCKED` setzen, unlock, session end.
5. Optional Snapshot für PR:
```bash
python /Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/shared_memory.py snapshot \
  --output /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/shared_memory_snapshot.json
```

## Verbindliche Referenzen
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/TAB_PATH_MANIFEST.md`
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/TAB_OWNERSHIP_RULES.md`
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/CODEX_PROJECT_ASSIGNMENTS.md`
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/check_domain_overlap.py`
- `/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/fleet_focus.py`

