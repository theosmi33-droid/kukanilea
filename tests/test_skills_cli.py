from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env(tmp_path: Path, mock_file: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["KUKANILEA_USER_DATA_ROOT"] = str(tmp_path / "ud")
    env["KUKANILEA_DB_FILENAME"] = str(tmp_path / "core.db")
    env["KUKANILEA_SKILLS_HTTP_MOCK"] = str(mock_file)
    return env


def test_cli_add_activate_quarantine(tmp_path: Path) -> None:
    mock_data = {
        "https://raw.githubusercontent.com/acme/repo/main/skills/demo/SKILL.md": {
            "status": 200,
            "text": "# Demo Skill\n",
        },
        "https://raw.githubusercontent.com/acme/repo/main/skills/demo/skill.json": {
            "status": 404,
            "text": "",
        },
        "https://raw.githubusercontent.com/acme/repo/main/skills/demo/README.md": {
            "status": 404,
            "text": "",
        },
        "https://raw.githubusercontent.com/acme/repo/main/skills/demo/resources/index.json": {
            "status": 404,
            "text": "",
        },
        "https://api.github.com/repos/acme/repo/commits/main": {
            "status": 200,
            "text": json.dumps({"sha": "e" * 40}),
        },
    }
    mock_file = tmp_path / "http_mock.json"
    mock_file.write_text(json.dumps(mock_data))

    env = _env(tmp_path, mock_file)

    add = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.skills.cli",
            "add",
            "https://github.com/acme/repo",
            "--skill",
            "demo",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert add.returncode == 0, add.stderr
    add_json = json.loads(add.stdout.strip())
    assert add_json["status"] == "quarantine"
    skill_id = int(add_json["skill_id"])

    activate = subprocess.run(
        [sys.executable, "-m", "app.skills.cli", "activate", str(skill_id)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert activate.returncode == 0, activate.stderr
    pointer = json.loads(activate.stdout.strip())
    assert int(pointer["skill_id"]) == skill_id

    quarantine = subprocess.run(
        [sys.executable, "-m", "app.skills.cli", "quarantine", str(skill_id)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert quarantine.returncode == 0, quarantine.stderr
    out = json.loads(quarantine.stdout.strip())
    assert out["status"] == "quarantine"
