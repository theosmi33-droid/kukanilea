from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.update import (
    UpdateError,
    compute_sha256,
    install_update_from_archive,
    rollback_update,
)


def _write_app(path: Path, *, marker: str) -> None:
    (path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
    (path / "Contents" / "MacOS" / "KUKANILEA").write_text(marker, encoding="utf-8")


def _make_update_zip(path: Path, *, app_name: str, marker: str) -> Path:
    payload_root = path / "payload"
    app_root = payload_root / app_name
    _write_app(app_root, marker=marker)
    archive = path / "update.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in payload_root.rglob("*"):
            if file_path.is_file():
                rel = file_path.relative_to(payload_root)
                zf.write(file_path, rel.as_posix())
    return archive


def test_install_update_keeps_data_dir_and_creates_backup(tmp_path: Path) -> None:
    app_dir = tmp_path / "KUKANILEA.app"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / "core.sqlite3"
    db_file.write_text("keep-me", encoding="utf-8")
    _write_app(app_dir, marker="old-build")

    archive = _make_update_zip(tmp_path, app_name=app_dir.name, marker="new-build")
    result = install_update_from_archive(
        archive,
        app_dir=app_dir,
        data_dir=data_dir,
        expected_sha256=compute_sha256(archive),
    )

    assert Path(result["backup_dir"]).exists()
    assert (app_dir / "Contents" / "MacOS" / "KUKANILEA").read_text(
        encoding="utf-8"
    ) == "new-build"
    assert db_file.read_text(encoding="utf-8") == "keep-me"


def test_install_update_rejects_sha_mismatch_without_touching_app(
    tmp_path: Path,
) -> None:
    app_dir = tmp_path / "KUKANILEA.app"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_app(app_dir, marker="old-build")
    archive = _make_update_zip(tmp_path, app_name=app_dir.name, marker="new-build")

    with pytest.raises(UpdateError, match="SHA256"):
        install_update_from_archive(
            archive,
            app_dir=app_dir,
            data_dir=data_dir,
            expected_sha256="deadbeef" * 8,
        )

    assert (app_dir / "Contents" / "MacOS" / "KUKANILEA").read_text(
        encoding="utf-8"
    ) == "old-build"
    assert not (tmp_path / "KUKANILEA.app.backup").exists()


def test_rollback_restores_previous_build(tmp_path: Path) -> None:
    app_dir = tmp_path / "KUKANILEA.app"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_app(app_dir, marker="old-build")
    archive = _make_update_zip(tmp_path, app_name=app_dir.name, marker="new-build")
    install_update_from_archive(
        archive,
        app_dir=app_dir,
        data_dir=data_dir,
        expected_sha256=compute_sha256(archive),
    )

    rollback_update(app_dir=app_dir)
    assert (app_dir / "Contents" / "MacOS" / "KUKANILEA").read_text(
        encoding="utf-8"
    ) == "old-build"
