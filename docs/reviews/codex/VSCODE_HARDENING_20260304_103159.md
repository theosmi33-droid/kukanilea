# VSCode Hardening Report

## Auftrag
- Rolle: VSCode/DevEx Hardening Worker
- Scope: Nur Entwickler-Tooling, keine Fachlogik

## Durchgeführte Checks

### 1) scripts/dev/vscode_guardrails.sh --check
- Initial: fehlgeschlagen, da `.build_venv/bin/python` im Container nicht vorhanden war.
- Maßnahme: `scripts/dev/vscode_guardrails.sh` um Python3-Fallback erweitert.
- Ergebnis nach Anpassung: `vscode-configs: OK`.

### 2) scripts/dev/enforce_vscode_configs.py --check
- Initial: direkter Aufruf nicht ausführbar (`Permission denied`).
- Maßnahme: Ausführungsbit gesetzt (`chmod +x`) und Shebang genutzt.
- Ergebnis: `vscode-configs: OK`.

## Hardening-Maßnahmen

### A) Stabilität in frischen Worktrees / 4-Window-Fleet
- Guardrail-Runner fällt jetzt auf `python3` zurück, wenn `.build_venv` noch nicht vorhanden ist.
- Dadurch brechen Auto-Tasks in einzelnen Fenstern nicht mehr hart ab.

### B) Langsame Settings/Indexer/Autotasks optimiert
In `enforce_vscode_configs.py` wurden zusätzliche Policy-Defaults zentral erzwungen:
- Python-Analyse auf offene Dateien begrenzt
- Indexing deaktiviert
- zusätzliche `python.analysis.exclude`-Pfade
- automatische Task-/NPM-Erkennung deaktiviert
- TypeScript ATA deaktiviert
- Extension Auto-Update/Auto-Check deaktiviert
- erweitertes `files.watcherExclude` (venv/caches/node_modules)

### C) Folder-Open Auto-Task entschärft
- `KUKANILEA: VS Code Guardrails (Auto-Fix)` führt jetzt nur noch `--apply` aus (ohne Hook-Installation).
- Hook-Installation bleibt explizit als One-Time-/manueller Schritt verfügbar.
- Ziel: weniger konkurrierende Side-Effects bei parallelem Öffnen mehrerer VS-Code-Fenster.

## Validierung
- `bash scripts/dev/vscode_guardrails.sh --check` => OK
- `scripts/dev/enforce_vscode_configs.py --check` => OK

## Geänderte Dateien
- `scripts/dev/vscode_guardrails.sh`
- `scripts/dev/enforce_vscode_configs.py`
- `.vscode/tasks.json`
- `.vscode/settings.json` (durch Guardrail-Apply auf neue Defaults normalisiert)
- `docs/dev/VSCODE_GUARDRAILS.md`
