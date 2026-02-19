#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config
from app.demo_data import demo_tenant_id_from_name, seed_demo_dataset


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed idempotent demo data for pilot usage."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing demo tenant data first and recreate.",
    )
    parser.add_argument(
        "--tenant-name",
        default="DEMO AG",
        help="Display name for demo tenant (default: DEMO AG).",
    )
    parser.add_argument(
        "--tenant-id",
        default="",
        help="Explicit tenant id (default: derived from tenant-name).",
    )
    parser.add_argument(
        "--username",
        default="demo",
        help="Demo username for auth DB (default: demo).",
    )
    parser.add_argument(
        "--password",
        default="demo",
        help="Demo password for auth DB (default: demo).",
    )
    parser.add_argument(
        "--core-db",
        default=str(Config.CORE_DB),
        help="Path to core sqlite db.",
    )
    parser.add_argument(
        "--auth-db",
        default=str(Config.AUTH_DB),
        help="Path to auth sqlite db.",
    )
    parser.add_argument(
        "--documents-dir",
        default="",
        help="Optional directory for generated demo document fixtures.",
    )
    args = parser.parse_args()

    tenant_name = str(args.tenant_name or "DEMO AG").strip() or "DEMO AG"
    tenant_id = str(args.tenant_id or "").strip() or demo_tenant_id_from_name(
        tenant_name
    )

    documents_dir = (
        Path(args.documents_dir).expanduser() if args.documents_dir else None
    )

    summary = seed_demo_dataset(
        db_path=Path(args.core_db).expanduser(),
        auth_db_path=Path(args.auth_db).expanduser(),
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        force=bool(args.force),
        create_auth_user=True,
        demo_username=str(args.username),
        demo_password=str(args.password),
        documents_root=documents_dir,
    )
    print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
