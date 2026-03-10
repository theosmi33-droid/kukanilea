from __future__ import annotations

import logging
from pathlib import Path

from app.core.auto_evolution import SystemHealer


def test_apply_hotfixes_writes_to_writable_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    writable_root = tmp_path / "runtime"
    repo_root.mkdir(parents=True)
    writable_root.mkdir(parents=True)

    healer = SystemHealer(
        db_path=tmp_path / "core.sqlite3",
        repo_root=repo_root,
        writable_root=writable_root,
    )
    healer.apply_hotfixes()

    expected = [
        "logs/crash",
        "vault",
        "trash",
        "instance/backups",
    ]
    for rel in expected:
        assert (writable_root / rel).is_dir()
        assert not (repo_root / rel).exists()


def test_apply_hotfixes_handles_directory_creation_errors(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    repo_root = tmp_path / "repo"
    writable_root = tmp_path / "runtime"
    repo_root.mkdir(parents=True)
    writable_root.mkdir(parents=True)

    def _raise_permission_error(self: Path, *args, **kwargs) -> None:  # pragma: no cover - exercised via monkeypatch
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "mkdir", _raise_permission_error)

    healer = SystemHealer(
        db_path=tmp_path / "core.sqlite3",
        repo_root=repo_root,
        writable_root=writable_root,
    )
    with caplog.at_level(logging.WARNING, logger="kukanilea.healer"):
        healer.apply_hotfixes()

    assert "Skipping hotfix directory setup" in caplog.text
