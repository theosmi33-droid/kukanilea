from __future__ import annotations

from pathlib import Path

from app.core.tenant_registry import TenantRegistry


def test_tenant_path_must_stay_inside_tenant_root(tmp_path: Path):
    registry = TenantRegistry(storage_path=tmp_path / "tenant_mapping.json")
    registry.tenants_root = tmp_path / "tenants"
    registry.tenants_root.mkdir(parents=True, exist_ok=True)

    tenant_root = registry.tenants_root / "acme"
    tenant_root.mkdir(parents=True, exist_ok=True)
    allowed_db = tenant_root / "core.sqlite3"
    allowed_db.write_text("", encoding="utf-8")

    other_root = registry.tenants_root / "other"
    other_root.mkdir(parents=True, exist_ok=True)
    other_db = other_root / "other.sqlite3"
    other_db.write_text("", encoding="utf-8")

    outside = tmp_path / "outside.sqlite3"
    outside.write_text("", encoding="utf-8")

    assert registry.validate_path(str(allowed_db), tenant_id="acme") is True
    assert registry.validate_path(str(other_db), tenant_id="acme") is False
    assert registry.validate_path(str(outside), tenant_id="acme") is False


def test_tenant_symlink_rejected(tmp_path: Path):
    registry = TenantRegistry(storage_path=tmp_path / "tenant_mapping.json")
    registry.tenants_root = tmp_path / "tenants"
    registry.tenants_root.mkdir(parents=True, exist_ok=True)

    tenant_root = registry.tenants_root / "acme"
    tenant_root.mkdir(parents=True, exist_ok=True)

    target = tmp_path / "sensitive.sqlite3"
    target.write_text("", encoding="utf-8")
    symlink_path = tenant_root / "db.sqlite3"
    symlink_path.symlink_to(target)

    assert registry.validate_path(str(symlink_path), tenant_id="acme") is False


def test_add_tenant_enforces_normalized_id_and_isolation(tmp_path: Path):
    registry = TenantRegistry(storage_path=tmp_path / "tenant_mapping.json")
    registry.tenants_root = tmp_path / "tenants"
    registry.tenants_root.mkdir(parents=True, exist_ok=True)

    valid_id = registry.normalize_tenant_id("ACME GmbH 2026")
    assert valid_id == "acme_gmbh_2026"

    tenant_root = registry.tenants_root / valid_id
    tenant_root.mkdir(parents=True, exist_ok=True)
    db_path = tenant_root / "tenant.sqlite3"
    db_path.write_text("", encoding="utf-8")

    assert registry.add_tenant(valid_id, "ACME GmbH 2026", str(db_path)) is True
    assert registry.get_tenant(valid_id) is not None

    outside_db = tmp_path / "outside.sqlite3"
    outside_db.write_text("", encoding="utf-8")
    assert registry.add_tenant(valid_id, "ACME GmbH 2026", str(outside_db)) is False


def test_tenant_registry_atomic_save(tmp_path: Path):
    import json
    import os
    mapping_path = tmp_path / "tenant_mapping.json"
    registry = TenantRegistry(storage_path=mapping_path)
    registry.tenants_root = tmp_path / "tenants"
    registry.tenants_root.mkdir(parents=True, exist_ok=True)

    # Add a tenant
    tenant_id = "acme"
    tenant_name = "ACME"
    db_path = registry.tenants_root / "acme" / "core.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("", encoding="utf-8")

    assert registry.add_tenant(tenant_id, tenant_name, str(db_path)) is True
    assert mapping_path.exists()
    
    # Verify content
    with open(mapping_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "acme" in data

    # Try to add same tenant again - should fail due to check
    assert registry.add_tenant(tenant_id, "ACME 2", str(db_path)) is False

    # Check permissions (0o600)
    mode = os.stat(mapping_path).st_mode & 0o777
    assert mode == 0o600
