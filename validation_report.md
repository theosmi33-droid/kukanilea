Drift detected: Cannot be directly determined due to '.gitignore' preventing access to .vscode/ directories.

Codex fix commands:
To apply fixes for the current repository and any detected worktrees, execute the following command from the root of the 'kukanilea_production' directory:
```bash
/Users/gensuminguyen/Kukanilea/kukanilea_production/scripts/dev/enforce_vscode_configs.py --apply
```

Final validation status:
Due to the '.vscode/' directory being ignored by '.gitignore', I cannot directly validate the VS Code interpreter/debug settings. The expected configurations, as per 'scripts/dev/enforce_vscode_configs.py', are:

For each worktree (including 'kukanilea_production' itself) in its '.vscode/settings.json':
- "python.defaultInterpreterPath": "${workspaceFolder}/.build_venv/bin/python" (for the root project) or "${workspaceFolder}/../kukanilea_production/.build_venv/bin/python" (for external worktrees)
- "python.terminal.activateEnvironment": true

For each worktree in its '.vscode/launch.json':
- Must contain a debug configuration named "KUKANILEA: Debug App 5051" with the following properties:
  - "type": "debugpy"
  - "request": "launch"
  - "python": (one of the allowed interpreter paths as above)
  - "program": "${workspaceFolder}/kukanilea_app.py"
  - "args": ["--host", "127.0.0.1", "--port", "5051"]
  - "console": "integratedTerminal"
  - "cwd": "${workspaceFolder}"
  - "justMyCode": false

For the 'fleet_root' (which is the parent directory of 'kukanilea_production'):
- In '.vscode/settings.json':
  - "python.defaultInterpreterPath": (absolute path to .build_venv/bin/python in kukanilea_production)
  - "python.useEnvironmentsExtension": true
  - "task.allowAutomaticTasks": "on"
- In 'kukanilea.code-workspace' (if it exists):
  - "settings.python.defaultInterpreterPath": (absolute path to .build_venv/bin/python in kukanilea_production)
  - "settings.python.useEnvironmentsExtension": true
  - "settings.task.allowAutomaticTasks": "on"

To manually validate, you would need to:
1. Navigate to each relevant directory (kukanilea_production, and any worktrees under its parent's 'worktrees' directory, e.g., ../worktrees/dashboard).
2. Open the '.vscode/settings.json' and '.vscode/launch.json' files in a text editor.
3. Compare their contents against the expected configurations listed above.
4. Also check the global settings files located at the 'fleet_root' directory (parent of kukanilea_production) for consistency.

NEEDS_CODEX: yes