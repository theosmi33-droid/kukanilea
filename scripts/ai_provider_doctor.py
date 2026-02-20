#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ai.provider_router import (  # noqa: E402
    provider_effective_policy,
    provider_health_snapshot,
    provider_order_from_env,
    provider_specs_public,
)


def _parse_roles(raw: str) -> list[str]:
    values = [part.strip().upper() for part in str(raw or "").split(",")]
    out = [v for v in values if v]
    return out or ["READONLY", "OPERATOR", "ADMIN", "DEV"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose der aktiven AI-Provider pro Tenant/Rolle."
    )
    parser.add_argument("--tenant", default="KUKANILEA")
    parser.add_argument("--roles", default="READONLY,OPERATOR,ADMIN,DEV")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    order = provider_order_from_env()
    report: dict[str, Any] = {"tenant": args.tenant, "order": order, "roles": []}
    for role in _parse_roles(args.roles):
        specs = provider_specs_public(order=order, tenant_id=args.tenant, role=role)
        health = provider_health_snapshot(order=order, tenant_id=args.tenant, role=role)
        policy = provider_effective_policy(tenant_id=args.tenant, role=role)
        report["roles"].append(
            {
                "role": role,
                "policy": policy,
                "provider_specs": specs,
                "provider_health": health.get("providers")
                if isinstance(health, dict)
                else [],
            }
        )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"Tenant: {report['tenant']}")
    print(f"Order:  {', '.join(report['order'])}")
    for row in report["roles"]:
        print(f"\n[{row['role']}]")
        specs = row["provider_specs"] or []
        if not specs:
            print("  providers: none (blocked by policy)")
            continue
        names = [str(p.get("type") or "") for p in specs]
        print(f"  providers: {', '.join(names)}")
        health_by = {
            str(h.get("provider") or ""): bool(h.get("healthy"))
            for h in (row["provider_health"] or [])
            if isinstance(h, dict)
        }
        for name in names:
            print(f"  - {name}: {'healthy' if health_by.get(name) else 'unhealthy'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
