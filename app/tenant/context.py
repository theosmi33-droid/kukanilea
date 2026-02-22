from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.license import load_license

TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    tenant_name: str


def _now_iso() -> str:
    return (
        datetime.now(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def is_valid_tenant_id(value: str) -> bool:
    token = str(value or "").strip()
    if not token:
        return False
    return bool(TENANT_ID_PATTERN.match(token))


def _normalize_tenant_name(value: str, fallback: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return str(fallback or "KUKANILEA").strip() or "KUKANILEA"
    return raw[:120]


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def _ensure_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_config (
          id TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          tenant_name TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
    )


def _license_tenant_payload(license_path: Path) -> dict[str, Any]:
    info = load_license(license_path)
    payload = info.get("payload")
    if not isinstance(payload, dict):
        return {}
    return payload


def _infer_tenant_from_sources(
    *,
    license_path: Path,
    fallback_tenant_id: str,
    fallback_tenant_name: str,
) -> TenantContext:
    env_tenant_id = str(os.environ.get("KUKANILEA_FIXED_TENANT_ID") or "").strip()
    env_tenant_name = str(os.environ.get("KUKANILEA_TENANT_NAME") or "").strip()
    payload = _license_tenant_payload(license_path)

    candidate_ids = [
        str(payload.get("tenant_id") or "").strip(),
        str(payload.get("tenant") or "").strip(),
        env_tenant_id,
        str(fallback_tenant_id or "").strip(),
    ]
    tenant_id = ""
    for value in candidate_ids:
        if is_valid_tenant_id(value):
            tenant_id = value
            break
    if not tenant_id:
        raise RuntimeError("Tenant not configured (missing fixed tenant id).")

    candidate_names = [
        str(payload.get("tenant_name") or "").strip(),
        str(payload.get("company") or "").strip(),
        str(payload.get("customer_name") or "").strip(),
        env_tenant_name,
        str(fallback_tenant_name or "").strip(),
        tenant_id,
    ]
    tenant_name = ""
    for value in candidate_names:
        if value:
            tenant_name = _normalize_tenant_name(value, tenant_id)
            break
    if not tenant_name:
        tenant_name = tenant_id

    return TenantContext(tenant_id=tenant_id, tenant_name=tenant_name)


def ensure_tenant_config(
    *,
    db_path: Path,
    license_path: Path,
    fallback_tenant_id: str,
    fallback_tenant_name: str,
) -> TenantContext:
    con = _connect(db_path)
    try:
        _ensure_table(con)
        row = con.execute(
            "SELECT tenant_id, tenant_name FROM tenant_config WHERE id='fixed' LIMIT 1"
        ).fetchone()
        if row:
            tenant_id = str(row["tenant_id"] or "").strip()
            tenant_name = str(row["tenant_name"] or "").strip()
            if not is_valid_tenant_id(tenant_id):
                raise RuntimeError("Invalid tenant_id in tenant_config.")
            if not tenant_name:
                tenant_name = tenant_id
            return TenantContext(tenant_id=tenant_id, tenant_name=tenant_name)

        ctx = _infer_tenant_from_sources(
            license_path=license_path,
            fallback_tenant_id=fallback_tenant_id,
            fallback_tenant_name=fallback_tenant_name,
        )
        con.execute(
            """
            INSERT INTO tenant_config(id, tenant_id, tenant_name, updated_at)
            VALUES ('fixed', ?, ?, ?)
            """,
            (ctx.tenant_id, ctx.tenant_name, _now_iso()),
        )
        con.commit()
        return ctx
    finally:
        con.close()


def load_tenant_context(db_path: Path) -> TenantContext | None:
    con = _connect(db_path)
    try:
        _ensure_table(con)
        row = con.execute(
            "SELECT tenant_id, tenant_name FROM tenant_config WHERE id='fixed' LIMIT 1"
        ).fetchone()
        if not row:
            return None
        tenant_id = str(row["tenant_id"] or "").strip()
        tenant_name = str(row["tenant_name"] or "").strip()
        if not is_valid_tenant_id(tenant_id):
            return None
        if not tenant_name:
            tenant_name = tenant_id
        return TenantContext(tenant_id=tenant_id, tenant_name=tenant_name)
    finally:
        con.close()


def update_tenant_name(db_path: Path, tenant_name: str) -> TenantContext:
    con = _connect(db_path)
    try:
        _ensure_table(con)
        row = con.execute(
            "SELECT tenant_id, tenant_name FROM tenant_config WHERE id='fixed' LIMIT 1"
        ).fetchone()
        if not row:
            raise RuntimeError("Tenant configuration missing.")
        tenant_id = str(row["tenant_id"] or "").strip()
        if not is_valid_tenant_id(tenant_id):
            raise RuntimeError("Invalid tenant configuration.")
        next_name = _normalize_tenant_name(tenant_name, tenant_id)
        con.execute(
            "UPDATE tenant_config SET tenant_name=?, updated_at=? WHERE id='fixed'",
            (next_name, _now_iso()),
        )
        con.commit()
        return TenantContext(tenant_id=tenant_id, tenant_name=next_name)
    finally:
        con.close()
