from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from app.core.inplace_update import InPlaceUpdater, UpdateError


def _updater(tmp_path: Path) -> InPlaceUpdater:
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return InPlaceUpdater(install_root=install_root, data_dir=data_dir)


def _empty_file_tarinfo(name: str, payload: bytes = b"x") -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    return info


def test_rejects_symlink_entries_in_update_tarball(tmp_path: Path):
    updater = _updater(tmp_path)
    tarball = tmp_path / "payload-symlink.tar"

    with tarfile.open(tarball, "w") as tf:
        info = tarfile.TarInfo(name="release/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../etc/passwd"
        tf.addfile(info)

    with pytest.raises(UpdateError, match="Unsupported entry type"):
        updater.apply_from_tarball(tarball, "v2")


def test_rejects_hardlink_entries_in_update_tarball(tmp_path: Path):
    updater = _updater(tmp_path)
    tarball = tmp_path / "payload-hardlink.tar"

    with tarfile.open(tarball, "w") as tf:
        target = _empty_file_tarinfo("release/app.py", b"print('ok')\n")
        tf.addfile(target, io.BytesIO(b"print('ok')\n"))

        link = tarfile.TarInfo(name="release/link-hard")
        link.type = tarfile.LNKTYPE
        link.linkname = "release/app.py"
        tf.addfile(link)

    with pytest.raises(UpdateError, match="Unsupported entry type"):
        updater.apply_from_tarball(tarball, "v2")


def test_rejects_absolute_path_entries_in_update_tarball(tmp_path: Path):
    updater = _updater(tmp_path)
    tarball = tmp_path / "payload-abs.tar"

    with tarfile.open(tarball, "w") as tf:
        info = _empty_file_tarinfo("/abs/escape.txt", b"bad")
        tf.addfile(info, io.BytesIO(b"bad"))

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_rejects_dotdot_normalized_paths_in_update_tarball(tmp_path: Path):
    updater = _updater(tmp_path)
    tarball = tmp_path / "payload-dotdot.tar"

    with tarfile.open(tarball, "w") as tf:
        info = _empty_file_tarinfo("release/../../escape.txt", b"bad")
        tf.addfile(info, io.BytesIO(b"bad"))

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")

