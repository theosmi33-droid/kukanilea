from __future__ import annotations

from pathlib import Path


def _repo_files(root: Path) -> set[str]:
    return {
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    }


def test_no_mirrored_files_between_app_static_and_root_static() -> None:
    app_static = Path("app/static")
    root_static = Path("static")

    app_files = _repo_files(app_static)
    root_files = _repo_files(root_static)
    mirrored = sorted(app_files & root_files)

    assert mirrored == [], (
        "Found mirrored static assets in both app/static and static. "
        "Keep a single source of truth under app/static and remove root/static duplicates: "
        f"{mirrored}"
    )
