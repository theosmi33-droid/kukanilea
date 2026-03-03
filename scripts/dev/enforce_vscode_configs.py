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

    # Keep VS Code Source Control responsive in large multi-worktree setups.
    if data.get("git.autoRepositoryDetection") != "openEditors":
        changes.append("git.autoRepositoryDetection")
        data["git.autoRepositoryDetection"] = "openEditors"
    if data.get("git.openRepositoryInParentFolders") != "never":
        changes.append("git.openRepositoryInParentFolders")
        data["git.openRepositoryInParentFolders"] = "never"
    if data.get("git.untrackedChanges") != "mixed":
        changes.append("git.untrackedChanges")
        data["git.untrackedChanges"] = "mixed"
    if data.get("git.repositoryScanMaxDepth") != 2:
        changes.append("git.repositoryScanMaxDepth")
        data["git.repositoryScanMaxDepth"] = 2

    watcher_exclude = data.get("files.watcherExclude")
    if not isinstance(watcher_exclude, dict):
        watcher_exclude = {}
        data["files.watcherExclude"] = watcher_exclude
        changes.append("files.watcherExclude")

    desired_watcher = {
        "**/.git/objects/**": True,
        "**/.git/subtree-cache/**": True,
        "**/.build_venv/**": True,
        "**/__pycache__/**": True,
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
    if data.get("task.allowAutomaticTasks") != "on":
        data["task.allowAutomaticTasks"] = "on"
        changes.append("task.allowAutomaticTasks")
    if data.get("git.autoRepositoryDetection") != "openEditors":
        data["git.autoRepositoryDetection"] = "openEditors"
        changes.append("git.autoRepositoryDetection")
    if data.get("git.openRepositoryInParentFolders") != "never":
        data["git.openRepositoryInParentFolders"] = "never"
        changes.append("git.openRepositoryInParentFolders")
    if data.get("git.untrackedChanges") != "mixed":
        data["git.untrackedChanges"] = "mixed"
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
    if settings.get("task.allowAutomaticTasks") != "on":
        settings["task.allowAutomaticTasks"] = "on"
        changes.append("settings.task.allowAutomaticTasks")
    if settings.get("git.autoRepositoryDetection") != "openEditors":
        settings["git.autoRepositoryDetection"] = "openEditors"
        changes.append("settings.git.autoRepositoryDetection")
    if settings.get("git.openRepositoryInParentFolders") != "never":
        settings["git.openRepositoryInParentFolders"] = "never"
        changes.append("settings.git.openRepositoryInParentFolders")
    if settings.get("git.untrackedChanges") != "mixed":
        settings["git.untrackedChanges"] = "mixed"
        changes.append("settings.git.untrackedChanges")
    if settings.get("git.repositoryScanMaxDepth") != 2:
        settings["git.repositoryScanMaxDepth"] = 2
        changes.append("settings.git.repositoryScanMaxDepth")

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
            preferred_interpreter = "${workspaceFolder}/../kukanilea_production/.build_venv/bin/python"
            absolute_interpreter = str(root / ".build_venv" / "bin" / "python")
        allowed_interpreters = {preferred_interpreter, absolute_interpreter}

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
