from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from app import create_app
from app.modules.projects.logic import ProjectManager

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "pr_quality_guard.sh"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)


def _run_guard(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--repo-root",
            str(repo),
            "--base-branch",
            "main",
        ],
        cwd=repo,
        check=False,
        text=True,
        capture_output=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], repo)
    _run(["git", "config", "user.email", "test@example.com"], repo)
    _run(["git", "config", "user.name", "Test User"], repo)
    (repo / "README.md").write_text("seed\n")
    (repo / "docs" / "reviews" / "codex").mkdir(parents=True)
    (repo / "docs" / "reviews" / "codex" / "PR_QUALITY_GUARD_REPORT_20260305.md").write_text("ok\n")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "seed"], repo)
    _run(["git", "checkout", "-b", "codex/20260305-feature"], repo)
    return repo


def test_pr_quality_guard_fails_for_thin_pr(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "small.txt").write_text("tiny\n")
    _run(["git", "add", "small.txt"], repo)
    _run(["git", "commit", "-m", "thin"], repo)

    result = _run_guard(repo)

    assert result.returncode != 0
    assert "MIN_SCOPE gate failed" in result.stdout


def test_pr_quality_guard_passes_for_solid_pr(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    for idx in range(1, 8):
        file_path = repo / "feature" / "work" / f"src_{idx}.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("x\n" * 20)

    test_file = repo / "tests" / "quality" / "test_quality_guard.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text(
        """

def test_a():
    assert True

def test_b():
    assert True

def test_c():
    assert True
""".strip()
        + "\n"
    )

    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "solid"], repo)

    result = _run_guard(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PR_QUALITY_GUARD: PASS" in result.stdout


def test_pr_quality_guard_fails_on_unfocused_scope(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    overlap_target = repo / "shared.txt"
    overlap_target.write_text("base\n")
    _run(["git", "add", "shared.txt"], repo)
    _run(["git", "commit", "-m", "add shared"], repo)

    _run(["git", "checkout", "main"], repo)
    _run(["git", "checkout", "-b", "codex/20260305-other"], repo)
    overlap_target.write_text("other branch\n")
    _run(["git", "add", "shared.txt"], repo)
    _run(["git", "commit", "-m", "other touches shared"], repo)

    _run(["git", "checkout", "codex/20260305-feature"], repo)
    overlap_target.write_text("feature branch\n")
    for idx in range(1, 7):
        (repo / f"scope_{idx}.txt").write_text("scope\n" * 40)
    test_file = repo / "tests" / "test_overlap_guard.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("\n".join([f"def test_{i}():\n    assert True" for i in range(6)]) + "\n")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "feature touches shared too"], repo)

    result = _run_guard(repo)

    assert result.returncode != 0
    assert "Lane overlap check failed" in result.stdout


def test_pr_quality_guard_fails_on_stacked_codex_branch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    _run(["git", "checkout", "main"], repo)
    _run(["git", "checkout", "-b", "codex/20260305-other"], repo)
    (repo / "other_scope.txt").write_text("other\n")
    _run(["git", "add", "other_scope.txt"], repo)
    _run(["git", "commit", "-m", "other scope change"], repo)

    _run(["git", "checkout", "codex/20260305-feature"], repo)
    _run(["git", "merge", "--no-ff", "--no-edit", "codex/20260305-other"], repo)

    result = _run_guard(repo)

    assert result.returncode != 0
    assert "Branch context gate failed" in result.stdout


def test_project_manager_migrates_legacy_team_tasks_schema(tmp_path: Path, monkeypatch) -> None:
    auth_db = tmp_path / "auth.sqlite3"
    con = sqlite3.connect(auth_db)
    try:
        con.execute(
            """
            CREATE TABLE team_tasks(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              board_id TEXT,
              title TEXT NOT NULL,
              description TEXT,
              priority TEXT NOT NULL DEFAULT 'MEDIUM',
              due_at TEXT,
              status TEXT NOT NULL DEFAULT 'OPEN',
              created_by TEXT NOT NULL,
              assigned_to TEXT,
              rejection_reason TEXT,
              source_type TEXT,
              source_ref TEXT,
              parent_task_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        con.execute(
            """
            INSERT INTO team_tasks(
              id, tenant_id, board_id, title, description, priority, due_at, status,
              created_by, assigned_to, rejection_reason, source_type, source_ref,
              parent_task_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "legacy-1",
                "KUKANILEA",
                "legacy-board",
                "Legacy row",
                "",
                "MEDIUM",
                None,
                "OPEN",
                "dev",
                "dev",
                None,
                None,
                None,
                None,
            ),
        )
        con.commit()
    finally:
        con.close()

    monkeypatch.setenv("KUKANILEA_AUTH_DB", str(auth_db))
    monkeypatch.setenv("KUKANILEA_CORE_DB", str(tmp_path / "core.sqlite3"))
    app = create_app()
    manager = ProjectManager(app.extensions["auth_db"])

    con = sqlite3.connect(auth_db)
    con.row_factory = sqlite3.Row
    try:
        columns = {row["name"] for row in con.execute("PRAGMA table_info(team_tasks)").fetchall()}
        row = con.execute(
            "SELECT board_id, project_id, project_board_id, project_card_id FROM team_tasks WHERE id = ?",
            ("legacy-1",),
        ).fetchone()
    finally:
        con.close()

    assert manager is not None
    assert {"project_id", "project_board_id", "project_card_id"}.issubset(columns)
    assert row is not None
    assert row["board_id"] == "legacy-board"
    assert row["project_board_id"] == "legacy-board"
    assert row["project_id"] is None
    assert row["project_card_id"] is None
