#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.tool_loader import load_all_tools
from app.tools.action_registry import action_registry


def build_catalog() -> Dict[str, Any]:
    load_all_tools()
    return {
        "action_count": action_registry.count(),
        "tools": action_registry.tools_summary(),
        "actions": action_registry.list_actions(),
    }


def to_markdown(catalog: Dict[str, Any]) -> str:
    lines = [
        "# Action Registry Catalog",
        "",
        f"Total actions: **{catalog['action_count']}**",
        "",
        "## Actions per tool",
        "",
        "| Tool | Actions |",
        "|---|---:|",
    ]
    for tool, count in sorted(catalog["tools"].items()):
        lines.append(f"| `{tool}` | {count} |")

    lines.extend(["", "## Action list", "", "| Action | Critical | Permissions | Audit fields |", "|---|---|---|---|"])
    for item in catalog["actions"]:
        perms = ", ".join(item.get("permissions") or []) or "-"
        audit = ", ".join(item.get("audit_fields") or []) or "-"
        lines.append(
            f"| `{item['name']}` | {'yes' if item.get('is_critical') else 'no'} | {perms} | {audit} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate action registry catalog")
    parser.add_argument("--json-out", default="evidence/operations/action_catalog.json")
    parser.add_argument("--md-out", default="docs/ai/action_registry_catalog.md")
    args = parser.parse_args()

    catalog = build_catalog()

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(to_markdown(catalog), encoding="utf-8")

    print(json.dumps({"action_count": catalog["action_count"], "json": str(json_path), "md": str(md_path)}))


if __name__ == "__main__":
    main()
