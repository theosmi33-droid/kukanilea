from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.core.inplace_update import InPlaceUpdater, UpdateError


def _seed_release(path: Path, version_text: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "app_version.txt").write_text(version_text, encoding="utf-8")
    (path / "run.py").write_text("print('ok')\n", encoding="utf-8")


def test_apply_update_keeps_data_dir_and_switches_current_atomically(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    (data_dir / "core.sqlite3").write_text("customer-db", encoding="utf-8")

    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    old_release = install_root / "releases" / "v1"
    _seed_release(old_release, "v1")
    os.symlink(old_release, install_root / "current")

    source_v2 = tmp_path / "incoming" / "v2"
    _seed_release(source_v2, "v2")

    result = updater.apply_from_directory(
        source_v2,
        "v2",
        healthcheck_cmd=[
            sys.executable,
            "-c",
            "from pathlib import Path;import sys;sys.exit(0 if Path('run.py').exists() else 1)",
        ],
    )

    assert result.version == "v2"
    assert (install_root / "current").resolve() == install_root / "releases" / "v2"
    assert result.previous_release == old_release
    assert (data_dir / "core.sqlite3").read_text(encoding="utf-8") == "customer-db"


def test_failed_healthcheck_rolls_back_to_previous_release(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)

    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    old_release = install_root / "releases" / "v1"
    _seed_release(old_release, "v1")
    os.symlink(old_release, install_root / "current")

    source_v2 = tmp_path / "incoming" / "v2"
    _seed_release(source_v2, "v2")

    with pytest.raises(UpdateError):
        updater.apply_from_directory(
            source_v2,
            "v2",
            healthcheck_cmd=[sys.executable, "-c", "import sys;sys.exit(1)"],
        )

    assert (install_root / "current").resolve() == old_release
    assert not (install_root / "releases" / "v2").exists()


def test_rejects_install_and_data_dir_overlap(tmp_path: Path):
    install_root = tmp_path / "kukanilea"
    bad_data_dir = install_root / "instance"
    bad_data_dir.mkdir(parents=True)

    updater = InPlaceUpdater(install_root=install_root, data_dir=bad_data_dir)

    source_v2 = tmp_path / "incoming" / "v2"
    _seed_release(source_v2, "v2")

    with pytest.raises(UpdateError, match="Data directory must be outside install root"):
        updater.apply_from_directory(source_v2, "v2")
