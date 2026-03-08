from __future__ import annotations

import io
import os
import tarfile
from pathlib import Path

from app.core.inplace_update import InPlaceUpdater


def test_apply_from_safe_tarball_keeps_release_inside_install_root(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    old_release = install_root / "releases" / "v1"
    old_release.mkdir(parents=True, exist_ok=True)
    (old_release / "run.py").write_text("print('v1')\n", encoding="utf-8")
    os.symlink(old_release, install_root / "current")

    tarball = tmp_path / "payload-safe.tar"
    with tarfile.open(tarball, "w") as tf:
        folder = tarfile.TarInfo(name="release")
        folder.type = tarfile.DIRTYPE
        tf.addfile(folder)

        run_py = tarfile.TarInfo(name="release/run.py")
        run_py_data = b"print('v2')\n"
        run_py.size = len(run_py_data)
        tf.addfile(run_py, io.BytesIO(run_py_data))

    result = updater.apply_from_tarball(tarball, "v2")

    assert result.version == "v2"
    assert result.release_dir == install_root / "releases" / "v2"
    assert (install_root / "current").resolve() == install_root / "releases" / "v2"
    assert result.release_dir.resolve().is_relative_to(install_root.resolve())

