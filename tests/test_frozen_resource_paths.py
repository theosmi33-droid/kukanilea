from __future__ import annotations

from pathlib import Path

import app.__init__ as app_init


def test_resource_dir_defaults_to_repo_root() -> None:
    root = app_init._resource_dir()
    assert (root / "templates").exists()
    assert (root / "static").exists()


def test_resource_dir_uses_meipass_when_frozen(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "templates").mkdir()
    (tmp_path / "static").mkdir()
    monkeypatch.setattr(app_init.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_init.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert app_init._resource_dir() == tmp_path.resolve()
