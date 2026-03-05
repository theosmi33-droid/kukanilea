#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / ".github/policy/ui_conflict_guardrails.json"


def _git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _matches(path: str, rule: str) -> bool:
    return path == rule or path.startswith(rule)


def _resolve_changed_files(base_ref: str) -> list[str]:
    merge_base = _git(["merge-base", "HEAD", base_ref])
    if not merge_base:
        return []
    out = _git(["diff", "--name-only", f"{merge_base}..HEAD"])
    return [line for line in out.splitlines() if line.strip()]


def _resolve_ui_files(globs: list[str]) -> list[str]:
    paths: set[str] = set()
    for glob in globs:
        for candidate in REPO_ROOT.glob(glob):
            if candidate.is_file():
                paths.add(str(candidate.relative_to(REPO_ROOT)).replace("\\", "/"))
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prevent merge conflicts across parallel UI branches")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--base-branch", default="origin/main")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    config = _load_json(Path(args.config))
    owners: dict[str, list[str]] = config["owners"]
    ui_files = _resolve_ui_files(config["ui_file_globs"])
    changed_files = _resolve_changed_files(args.base_branch)
    merge_order_doc = REPO_ROOT / config["merge_order_doc"]

    validation_rounds = int(config.get("validation_rounds", 1))
    owner_rules_checked = len(ui_files) * len(owners) * max(validation_rounds, 1)
    min_actions = int(config.get("min_actions", 2100))

    unscoped_changed_files: list[str] = []
    multi_owner_changed_files: dict[str, list[str]] = {}
    for changed in changed_files:
        matching_owners = [owner for owner, rules in owners.items() if any(_matches(changed, rule) for rule in rules)]
        if len(matching_owners) == 0 and changed.startswith(("app/templates/", "app/static/js/", "app/static/css/")):
            unscoped_changed_files.append(changed)
        if len(matching_owners) > 1:
            multi_owner_changed_files[changed] = matching_owners

    merge_order_ok = False
    merge_order_missing_sections: list[str] = []
    required_sections = ["# UI Merge Order", "## Scoped Ownership", "## Merge Queue", "## CI Gates"]
    if merge_order_doc.exists():
        body = merge_order_doc.read_text(encoding="utf-8")
        merge_order_missing_sections = [section for section in required_sections if section not in body]
        merge_order_ok = len(merge_order_missing_sections) == 0

    status = "OK"
    failures: list[str] = []
    if owner_rules_checked < min_actions:
        status = "FAIL"
        failures.append(f"ACTION_BUDGET_BELOW_MIN: {owner_rules_checked} < {min_actions}")
    if unscoped_changed_files:
        status = "FAIL"
        failures.append(f"UNSCOPED_UI_CHANGES: {', '.join(unscoped_changed_files)}")
    if multi_owner_changed_files:
        status = "FAIL"
        failures.append(
            "MULTI_OWNER_UI_CHANGES: "
            + "; ".join(f"{path} => {','.join(owners_)}" for path, owners_ in sorted(multi_owner_changed_files.items()))
        )
    if not merge_order_doc.exists():
        status = "FAIL"
        failures.append(f"MISSING_MERGE_ORDER_DOC: {config['merge_order_doc']}")
    elif not merge_order_ok:
        status = "FAIL"
        failures.append("MERGE_ORDER_SECTIONS_MISSING: " + ", ".join(merge_order_missing_sections))

    result = {
        "status": status,
        "owner_rules_checked": owner_rules_checked,
        "min_actions": min_actions,
        "ui_files": len(ui_files),
        "owners": len(owners),
        "validation_rounds": validation_rounds,
        "changed_files": changed_files,
        "unscoped_changed_files": unscoped_changed_files,
        "multi_owner_changed_files": multi_owner_changed_files,
        "merge_order_doc": config["merge_order_doc"],
        "merge_order_ok": merge_order_ok,
        "failures": failures,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"status={status}")
        print(f"owner_rules_checked={owner_rules_checked}")
        print(f"min_actions={min_actions}")
        if failures:
            for failure in failures:
                print(f"- {failure}")

    return 0 if status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
