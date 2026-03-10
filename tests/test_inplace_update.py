from __future__ import annotations

import os
import sys
import tarfile
from io import BytesIO
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


def test_apply_from_tarball_rejects_path_traversal(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload.tar"
    with tarfile.open(tarball, "w") as tf:
        payload = tmp_path / "payload.txt"
        payload.write_text("malicious", encoding="utf-8")
        tf.add(payload, arcname="../escaped.txt")

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")

    assert not (tmp_path / "escaped.txt").exists()


def test_apply_from_tarball_rejects_absolute_member_paths(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-abs.tar"
    with tarfile.open(tarball, "w") as tf:
        payload = b"malicious"
        member = tarfile.TarInfo("/escaped.txt")
        member.size = len(payload)
        tf.addfile(member, fileobj=BytesIO(payload))

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_windows_style_backslash_traversal(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-win-traversal.tar"
    with tarfile.open(tarball, "w") as tf:
        payload = tmp_path / "payload.txt"
        payload.write_text("malicious", encoding="utf-8")
        tf.add(payload, arcname="..\\escaped.txt")

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_symbolic_links(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-symlink.tar"
    with tarfile.open(tarball, "w") as tf:
        symlink = tarfile.TarInfo("link-to-host")
        symlink.type = tarfile.SYMTYPE
        symlink.linkname = "../escaped.txt"
        tf.addfile(symlink)

    with pytest.raises(UpdateError, match="Unsupported entry type in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_windows_drive_prefixed_member_paths(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-drive-prefix.tar"
    with tarfile.open(tarball, "w") as tf:
        payload = b"malicious"
        member = tarfile.TarInfo("C:/escaped.txt")
        member.size = len(payload)
        tf.addfile(member, fileobj=BytesIO(payload))

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_normalized_escape_paths(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-normalized-escape.tar"
    with tarfile.open(tarball, "w") as tf:
        payload = b"malicious"
        member = tarfile.TarInfo("safe/../../escaped.txt")
        member.size = len(payload)
        tf.addfile(member, fileobj=BytesIO(payload))

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_hard_links(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-hardlink.tar"
    with tarfile.open(tarball, "w") as tf:
        hardlink = tarfile.TarInfo("hardlink-to-host")
        hardlink.type = tarfile.LNKTYPE
        hardlink.linkname = "../escaped.txt"
        tf.addfile(hardlink)

    with pytest.raises(UpdateError, match="Unsupported entry type in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_fifo_entries(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-fifo.tar"
    with tarfile.open(tarball, "w") as tf:
        fifo = tarfile.TarInfo("pipe-entry")
        fifo.type = tarfile.FIFOTYPE
        tf.addfile(fifo)

    with pytest.raises(UpdateError, match="Unsupported entry type in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_backslash_absolute_paths(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-backslash-abs.tar"
    with tarfile.open(tarball, "w") as tf:
        payload = b"malicious"
        member = tarfile.TarInfo("\\escaped.txt")
        member.size = len(payload)
        tf.addfile(member, fileobj=BytesIO(payload))

    with pytest.raises(UpdateError, match="Unsafe path in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_rejects_character_device_entries(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    tarball = tmp_path / "payload-chardev.tar"
    with tarfile.open(tarball, "w") as tf:
        chardev = tarfile.TarInfo("char-device")
        chardev.type = tarfile.CHRTYPE
        tf.addfile(chardev)

    with pytest.raises(UpdateError, match="Unsupported entry type in update archive"):
        updater.apply_from_tarball(tarball, "v2")


def test_apply_from_tarball_accepts_regular_payload_and_switches_release(tmp_path: Path):
    install_root = tmp_path / "opt" / "kukanilea"
    data_dir = tmp_path / "var" / "kukanilea-data"
    data_dir.mkdir(parents=True)
    updater = InPlaceUpdater(install_root=install_root, data_dir=data_dir)

    old_release = install_root / "releases" / "v1"
    _seed_release(old_release, "v1")
    os.symlink(old_release, install_root / "current")

    tarball = tmp_path / "payload-ok.tar"
    payload_root = tmp_path / "payload-ok"
    payload_root.mkdir(parents=True, exist_ok=True)
    _seed_release(payload_root, "v2")

    with tarfile.open(tarball, "w") as tf:
        tf.add(payload_root, arcname="kukanilea-update")

    result = updater.apply_from_tarball(
        tarball,
        "v2",
        healthcheck_cmd=[
            sys.executable,
            "-c",
            "from pathlib import Path;import sys;sys.exit(0 if Path('run.py').exists() else 1)",
        ],
    )

    assert result.version == "v2"
    assert (install_root / "current").resolve() == install_root / "releases" / "v2"
