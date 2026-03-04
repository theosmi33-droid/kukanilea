#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DOMAINS = [
    "dashboard",
    "upload",
    "emailpostfach",
    "messenger",
    "kalender",
    "aufgaben",
    "zeiterfassung",
    "projekte",
    "excel-docs-visualizer",
    "einstellungen",
    "floating-widget-chatbot",
]


def detect_repo_root() -> Path:
    cp = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode == 0 and cp.stdout.strip():
        return Path(cp.stdout.strip())
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def ensure_settings(path: Path, interpreter: str, allowed_interpreters: set[str], apply: bool) -> list[str]:
    changes: list[str] = []
    data = load_json(path)
    current = data.get("python.defaultInterpreterPath")
    if current not in allowed_interpreters:
        changes.append("python.defaultInterpreterPath")
        data["python.defaultInterpreterPath"] = interpreter
    if data.get("python.terminal.activateEnvironment") is not True:
        changes.append("python.terminal.activateEnvironment")
        data["python.terminal.activateEnvironment"] = True
    if data.get("python.useEnvironmentsExtension") is not True:
        changes.append("python.useEnvironmentsExtension")
        data["python.useEnvironmentsExtension"] = True

    desired_scalar = {
        "python.analysis.typeCheckingMode": "basic",
        "python.analysis.diagnosticMode": "openFilesOnly",
        "python.analysis.indexing": False,
        "python.analysis.autoImportCompletions": False,
        "python.experiments.enabled": False,
        "python.testing.pytestEnabled": False,
        "python.testing.unittestEnabled": False,
        "python.testing.autoTestDiscoverOnSaveEnabled": False,
        "python.testing.pytestArgs": [],
        "ruff.lint.run": "onType",
        "ruff.nativeServer": "on",
        "editor.formatOnSave": False,
        "files.eol": "\n",
        "files.trimTrailingWhitespace": True,
        "files.insertFinalNewline": True,
        "git.autofetch": True,
        "git.confirmSync": False,
        "githubPullRequests.pullBranch": "never",
        "terminal.integrated.defaultProfile.osx": "zsh-clean",
        "terminal.integrated.cwd": "${workspaceFolder}",
        "workbench.editor.enablePreview": False,
        "workbench.startupEditor": "none",
        "window.restoreWindows": "none",
        "search.followSymlinks": False,
        "task.allowAutomaticTasks": "off",
    }
    for key, value in desired_scalar.items():
        if data.get(key) != value:
            data[key] = value
            changes.append(key)

    code_actions = data.get("editor.codeActionsOnSave")
    if not isinstance(code_actions, dict):
        code_actions = {}
        data["editor.codeActionsOnSave"] = code_actions
        changes.append("editor.codeActionsOnSave")
    for key, value in {
        "source.fixAll": "explicit",
        "source.organizeImports": "explicit",
    }.items():
        if code_actions.get(key) != value:
            code_actions[key] = value
            changes.append(f"editor.codeActionsOnSave.{key}")

    analysis_exclude = data.get("python.analysis.exclude")
    if not isinstance(analysis_exclude, list):
        analysis_exclude = []
        data["python.analysis.exclude"] = analysis_exclude
        changes.append("python.analysis.exclude")
    for pattern in [
        "**/.git/**",
        "**/.build_venv/**",
        "**/.venv/**",
        "**/node_modules/**",
        "**/__pycache__/**",
        "**/.pytest_cache/**",
        "**/archive_legacy/**",
        "**/docs/reviews/**",
        "**/data/**",
        "**/instance/**",
    ]:
        if pattern not in analysis_exclude:
            analysis_exclude.append(pattern)
            changes.append(f"python.analysis.exclude.{pattern}")

    for key_name in ("files.exclude", "search.exclude"):
        current = data.get(key_name)
        if not isinstance(current, dict):
            current = {}
            data[key_name] = current
            changes.append(key_name)
        desired = {
            "**/.build_venv": True,
            "**/.venv": True,
            "**/node_modules": True,
            "**/.pytest_cache": True,
            "**/.ruff_cache": True,
            "**/__pycache__": True,
            "**/output": True,
            "**/artifacts": True,
            "**/playwright-report": True,
            "**/test-results": True,
            "docs/reviews/codex/LAUNCH_EVIDENCE_RUN_*.md": True,
            "docs/reviews/codex/OVERLAP_MATRIX_11_*.md": True,
            "docs/reviews/gemini/live/*_buildout_*.md": True,
            "docs/scope_requests/patches/*.patch": True,
        }
        for key, value in desired.items():
            if current.get(key) != value:
                current[key] = value
                changes.append(f"{key_name}.{key}")

    terminal_env = data.get("terminal.integrated.env.osx")
    if not isinstance(terminal_env, dict):
        terminal_env = {}
        data["terminal.integrated.env.osx"] = terminal_env
        changes.append("terminal.integrated.env.osx")
    desired_env = {
        "PYTHONUNBUFFERED": "1",
        "OLLAMA_ENABLED": "1",
        "KUKANILEA_REMOTE_LLM_ENABLED": "0",
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "GEMINI_DEFAULT_MODEL": "gemini-2.5-flash",
    }
    for key, value in desired_env.items():
        if terminal_env.get(key) != value:
            terminal_env[key] = value
            changes.append(f"terminal.integrated.env.osx.{key}")

    terminal_profiles = data.get("terminal.integrated.profiles.osx")
    if not isinstance(terminal_profiles, dict):
        terminal_profiles = {}
        data["terminal.integrated.profiles.osx"] = terminal_profiles
        changes.append("terminal.integrated.profiles.osx")
    zsh_profile = terminal_profiles.get("zsh-clean")
    desired_profile = {"path": "/bin/zsh", "args": ["-f", "-i"]}
    if not isinstance(zsh_profile, dict) or zsh_profile != desired_profile:
        terminal_profiles["zsh-clean"] = desired_profile
        changes.append("terminal.integrated.profiles.osx.zsh-clean")

    # Keep VS Code Source Control responsive in large multi-worktree setups.
    if data.get("git.autoRepositoryDetection") != "openEditors":
        changes.append("git.autoRepositoryDetection")
        data["git.autoRepositoryDetection"] = "openEditors"
    if data.get("git.openRepositoryInParentFolders") != "never":
        changes.append("git.openRepositoryInParentFolders")
        data["git.openRepositoryInParentFolders"] = "never"
    if data.get("git.untrackedChanges") != "hidden":
        changes.append("git.untrackedChanges")
        data["git.untrackedChanges"] = "hidden"
    if data.get("git.repositoryScanMaxDepth") != 2:
        changes.append("git.repositoryScanMaxDepth")
        data["git.repositoryScanMaxDepth"] = 2

    watcher_exclude = data.get("files.watcherExclude")
    if not isinstance(watcher_exclude, dict):
        watcher_exclude = {}
        data["files.watcherExclude"] = watcher_exclude
        changes.append("files.watcherExclude")

    desired_watcher = {
        "**/.git/**": True,
        "**/.git/objects/**": True,
        "**/.git/subtree-cache/**": True,
        "**/.build_venv/**": True,
        "**/.venv/**": True,
        "**/node_modules/**": True,
        "**/__pycache__/**": True,
        "**/docs/reviews/codex/LAUNCH_EVIDENCE_RUN_*.md": True,
        "**/docs/reviews/codex/OVERLAP_MATRIX_11_*.md": True,
        "**/docs/reviews/gemini/live/*_buildout_*.md": True,
    }
    for key, value in desired_watcher.items():
        if watcher_exclude.get(key) != value:
            watcher_exclude[key] = value
            changes.append(f"files.watcherExclude.{key}")
    if apply and changes:
        write_json(path, data)
    return changes


def ensure_launch(path: Path, interpreter: str, allowed_interpreters: set[str], apply: bool) -> list[str]:
    changes: list[str] = []
    data = load_json(path)
    if "version" not in data:
        data["version"] = "0.2.0"
        changes.append("version")
    configs = data.get("configurations")
    if not isinstance(configs, list):
        configs = []
        data["configurations"] = configs
    target = None
    for cfg in configs:
        if isinstance(cfg, dict) and cfg.get("name") == "KUKANILEA: Debug App 5051":
            target = cfg
            break
    if target is None:
        target = {
            "name": "KUKANILEA: Debug App 5051",
            "type": "debugpy",
            "request": "launch",
            "python": interpreter,
            "program": "${workspaceFolder}/kukanilea_app.py",
            "args": ["--host", "127.0.0.1", "--port", "5051"],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "justMyCode": False,
        }
        configs.append(target)
        changes.append("configurations[+]")
    else:
        expected = {
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/kukanilea_app.py",
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "justMyCode": False,
        }
        for key, value in expected.items():
            if target.get(key) != value:
                target[key] = value
                changes.append(f"configurations.{key}")
        args = ["--host", "127.0.0.1", "--port", "5051"]
        if target.get("args") != args:
            target["args"] = args
            changes.append("configurations.args")
        if target.get("python") not in allowed_interpreters:
            target["python"] = interpreter
            changes.append("configurations.python")
    if apply and changes:
        write_json(path, data)
    return changes


def ensure_global_settings_file(path: Path, interpreter: str, apply: bool) -> list[str]:
    changes: list[str] = []
    data = load_json(path)
    current = data.get("python.defaultInterpreterPath")
    if current != interpreter:
        data["python.defaultInterpreterPath"] = interpreter
        changes.append("python.defaultInterpreterPath")
    if data.get("python.useEnvironmentsExtension") is not True:
        data["python.useEnvironmentsExtension"] = True
        changes.append("python.useEnvironmentsExtension")
    if data.get("task.allowAutomaticTasks") != "off":
        data["task.allowAutomaticTasks"] = "off"
        changes.append("task.allowAutomaticTasks")
    if data.get("git.autoRepositoryDetection") != "openEditors":
        data["git.autoRepositoryDetection"] = "openEditors"
        changes.append("git.autoRepositoryDetection")
    if data.get("git.openRepositoryInParentFolders") != "never":
        data["git.openRepositoryInParentFolders"] = "never"
        changes.append("git.openRepositoryInParentFolders")
    if data.get("git.untrackedChanges") != "hidden":
        data["git.untrackedChanges"] = "hidden"
        changes.append("git.untrackedChanges")
    if data.get("git.repositoryScanMaxDepth") != 2:
        data["git.repositoryScanMaxDepth"] = 2
        changes.append("git.repositoryScanMaxDepth")
    if apply and changes:
        write_json(path, data)
    return changes


def ensure_workspace_file(path: Path, interpreter: str, apply: bool) -> list[str]:
    changes: list[str] = []
    data = load_json(path)
    settings = data.get("settings")
    if not isinstance(settings, dict):
        settings = {}
        data["settings"] = settings
        changes.append("settings")

    if settings.get("python.defaultInterpreterPath") != interpreter:
        settings["python.defaultInterpreterPath"] = interpreter
        changes.append("settings.python.defaultInterpreterPath")
    if settings.get("python.useEnvironmentsExtension") is not True:
        settings["python.useEnvironmentsExtension"] = True
        changes.append("settings.python.useEnvironmentsExtension")
    if settings.get("task.allowAutomaticTasks") != "off":
        settings["task.allowAutomaticTasks"] = "off"
        changes.append("settings.task.allowAutomaticTasks")
    if settings.get("git.autoRepositoryDetection") != "openEditors":
        settings["git.autoRepositoryDetection"] = "openEditors"
        changes.append("settings.git.autoRepositoryDetection")
    if settings.get("git.openRepositoryInParentFolders") != "never":
        settings["git.openRepositoryInParentFolders"] = "never"
        changes.append("settings.git.openRepositoryInParentFolders")
    if settings.get("git.untrackedChanges") != "hidden":
        settings["git.untrackedChanges"] = "hidden"
        changes.append("settings.git.untrackedChanges")
    if settings.get("git.repositoryScanMaxDepth") != 2:
        settings["git.repositoryScanMaxDepth"] = 2
        changes.append("settings.git.repositoryScanMaxDepth")

    for key_name in ("files.exclude", "search.exclude", "files.watcherExclude"):
        current = settings.get(key_name)
        if not isinstance(current, dict):
            current = {}
            settings[key_name] = current
            changes.append(f"settings.{key_name}")
        desired = {
            "**/.build_venv": True,
            "**/.venv": True,
            "**/node_modules": True,
            "**/.pytest_cache": True,
            "**/.ruff_cache": True,
            "**/__pycache__": True,
            "**/output": True,
            "**/artifacts": True,
            "**/playwright-report": True,
            "**/test-results": True,
            "**/.git/objects/**": True,
            "**/.git/subtree-cache/**": True,
            "**/.git/**": True,
            "**/.build_venv/**": True,
            "**/.venv/**": True,
            "**/node_modules/**": True,
            "docs/reviews/codex/LAUNCH_EVIDENCE_RUN_*.md": True,
            "docs/reviews/codex/OVERLAP_MATRIX_11_*.md": True,
            "docs/reviews/gemini/live/*_buildout_*.md": True,
            "docs/scope_requests/patches/*.patch": True,
        }
        for key, value in desired.items():
            if current.get(key) != value:
                current[key] = value
                changes.append(f"settings.{key_name}.{key}")

    if apply and changes:
        write_json(path, data)
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/enforce VS Code interpreter + debugpy configs")
    parser.add_argument("--apply", action="store_true", help="Write missing/fixed config values")
    parser.add_argument("--check", action="store_true", help="Fail if mismatches are found")
    args = parser.parse_args()

    if not args.apply and not args.check:
        args.check = True

    root = detect_repo_root()
    targets: list[Path] = [root]
    worktrees_root = root.parent / "worktrees"
    for domain in DOMAINS:
        wt = worktrees_root / domain
        if wt.exists():
            targets.append(wt)

    mismatches: list[str] = []
    for target in targets:
        if target == root:
            preferred_interpreter = "${workspaceFolder}/.build_venv/bin/python"
            absolute_interpreter = str(root / ".build_venv" / "bin" / "python")
        else:
            # Worktrees are siblings under /worktrees/*, so absolute path is safer and stable.
            absolute_interpreter = str(root / ".build_venv" / "bin" / "python")
            preferred_interpreter = absolute_interpreter
        allowed_interpreters = {
            preferred_interpreter,
            absolute_interpreter,
            "${workspaceFolder}/.build_venv/bin/python",
            "${workspaceFolder}/../kukanilea_production/.build_venv/bin/python",
        }

        vscode = target / ".vscode"
        settings = vscode / "settings.json"
        launch = vscode / "launch.json"

        settings_changes = ensure_settings(settings, preferred_interpreter, allowed_interpreters, apply=args.apply)
        launch_changes = ensure_launch(launch, preferred_interpreter, allowed_interpreters, apply=args.apply)

        if settings_changes or launch_changes:
            rel = str(target.relative_to(root.parent)).replace("\\", "/")
            msg = f"{rel}: settings={settings_changes or ['ok']} launch={launch_changes or ['ok']}"
            mismatches.append(msg)

    fleet_root = root.parent
    absolute_interpreter = str(root / ".build_venv" / "bin" / "python")
    global_settings_path = fleet_root / ".vscode" / "settings.json"
    global_workspace_path = fleet_root / "kukanilea.code-workspace"

    if global_settings_path.exists() or args.apply:
        changes = ensure_global_settings_file(global_settings_path, absolute_interpreter, apply=args.apply)
        if changes:
            rel = str(global_settings_path.relative_to(fleet_root)).replace("\\", "/")
            mismatches.append(f"{rel}: {changes}")

    if global_workspace_path.exists() or args.apply:
        changes = ensure_workspace_file(global_workspace_path, absolute_interpreter, apply=args.apply)
        if changes:
            rel = str(global_workspace_path.relative_to(fleet_root)).replace("\\", "/")
            mismatches.append(f"{rel}: {changes}")

    if mismatches:
        print("vscode-config-mismatches:")
        for row in mismatches:
            print(f"  - {row}")
        if args.check:
            return 1
    else:
        print("vscode-configs: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
