from __future__ import annotations

import argparse
import json

from app.config import Config
from app.demo_data import generate_demo_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo data for a tenant.")
    parser.add_argument("--tenant", default="dev", help="Tenant ID (default: dev)")
    args = parser.parse_args()

    summary = generate_demo_data(db_path=Config.CORE_DB, tenant_id=str(args.tenant))
    print(
        json.dumps({"ok": True, "tenant_id": args.tenant, "summary": summary}, indent=2)
    )


if __name__ == "__main__":
    main()
