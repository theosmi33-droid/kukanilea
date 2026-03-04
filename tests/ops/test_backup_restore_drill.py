from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path


def _run(cmd: list[str], env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, env=env, check=True, text=True, capture_output=True)


def test_backup_restore_drill_e2e(tmp_path: Path):
    repo = Path(__file__).resolve().parents[2]
    data_root = tmp_path / "instance"
    nas_root = tmp_path / "nas"
    env = os.environ.copy()
    env.update(
        {
            "KUKANILEA_USER_DATA_ROOT": str(data_root),
            "KUKANILEA_AUTH_DB": str(data_root / "auth.sqlite3"),
            "KUKANILEA_CORE_DB": str(data_root / "core.sqlite3"),
            "KUKANILEA_NAS_DIR": str(nas_root),
            "TENANT_DEFAULT": "KUKANILEA",
        }
    )

    _run(["python", "scripts/seed_demo_data.py"], env, repo)
    _run(["./scripts/ops/backup_to_nas.sh", "--real-run"], env, repo)

    with sqlite3.connect(data_root / "auth.sqlite3") as con:
        con.execute("DELETE FROM projects")
        con.commit()

    _run(["./scripts/ops/restore_from_nas.sh", "--real-run"], env, repo)
    _run(["python", "scripts/ops/restore_validation.py"], env, repo)

    output = _run(
        [
            "python",
            "scripts/ops/restore_validation.py",
            "compare",
            "--before",
            str(repo / "evidence/ops/last_restored_metrics.json"),
        ],
        env,
        repo,
    )
    result = json.loads(output.stdout)
    assert result["ok"] is True
