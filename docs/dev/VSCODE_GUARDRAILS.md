# VS Code Guardrails

This project enforces a stable VS Code setup for core + all 11 worktrees.

## What is automated

1. Interpreter and debugger config is validated/repaired with:
   `scripts/dev/enforce_vscode_configs.py`
2. Auto-fix runs when the workspace folder opens via task:
   `KUKANILEA: VS Code Guardrails (Auto-Fix)`.
3. Git pre-commit hook blocks common policy regressions:
   - VS Code config drift
   - external CDN references in staged changes

## One-time setup

```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production
bash scripts/dev/install_git_hooks.sh
```

## Manual commands

```bash
# check only
bash scripts/dev/vscode_guardrails.sh --check

# apply fixes only
bash scripts/dev/vscode_guardrails.sh --apply

# optional: apply + (re-)install hooks
bash scripts/dev/vscode_guardrails.sh --apply --install-hooks
```

If `.build_venv/bin/python` is missing, guardrails now fall back to `python3`
so checks still run in fresh or partially initialized worktrees.

## Policy defaults

- Core interpreter: `${workspaceFolder}/.build_venv/bin/python`
- Worktree interpreter: `${workspaceFolder}/../kukanilea_production/.build_venv/bin/python`
- Debugger type: `debugpy`
- Automatic tasks allowed: `task.allowAutomaticTasks = "on"`
- Background load reduction:
  - `python.analysis.diagnosticMode = "openFilesOnly"`
  - `python.analysis.indexing = false`
  - automatic Task/NPM detection is disabled
  - watcher excludes cover venv/cache/node_modules folders
