from __future__ import annotations

from pathlib import Path

from app.core.logic import _resolve_existing_folder


def test_resolve_existing_folder_allows_absolute_path_inside_tenant_dir(tmp_path) -> None:
    tenant_dir = tmp_path / "tenant-a"
    allowed = tenant_dir / "1234_obj"
    allowed.mkdir(parents=True)

    resolved = _resolve_existing_folder(str(allowed), tenant_dir)

    assert resolved == allowed.resolve()


def test_resolve_existing_folder_allows_relative_path_inside_tenant_dir(tmp_path) -> None:
    tenant_dir = tmp_path / "tenant-a"
    allowed = tenant_dir / "existing"
    allowed.mkdir(parents=True)

    resolved = _resolve_existing_folder("existing", tenant_dir)

    assert resolved == allowed.resolve()


def test_resolve_existing_folder_rejects_path_outside_tenant_dir(tmp_path) -> None:
    tenant_dir = tmp_path / "tenant-a"
    tenant_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)

    resolved = _resolve_existing_folder(str(outside), tenant_dir)

    assert resolved is None


def test_resolve_existing_folder_rejects_traversal_outside_tenant_dir(tmp_path) -> None:
    tenant_dir = tmp_path / "tenant-a"
    tenant_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)

    resolved = _resolve_existing_folder("../outside", tenant_dir)

    assert resolved is None
