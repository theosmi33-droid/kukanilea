#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SHARED_CORE = {
    "app/web.py",
    "app/core/logic.py",
    "app/__init__.py",
    "app/db.py",
    "app/templates/layout.html",
}

SHARED_CORE_PREFIXES = {
    "app/templates/partials/",
}

GLOBAL_IGNORES = (
    ".vscode/",
    "vscode/",
    "README_SCOPE.md",
    "docs/scope_requests/",
    "docs/scopes/",
    "docs/shared_memory_snapshot.json",
    "docs/AGENT_",
    "docs/FLEET_COMMANDER_",
    "docs/HANDOFF_GEMINI_",
    "docs/TAB_PATH_MANIFEST.md",
    "docs/VS_CODE_GEMINI_STARTCHECK_PROMPT.md",
    "scripts/shared_memory.py",
    "scripts/vscode_ready_check.sh",
)

ALLOWLIST: dict[str, list[str]] = {
    "dashboard": [
        "app/templates/dashboard.html",
        "app/templates/components/system_status.html",
        "app/core/observer.py",
        "app/core/auto_evolution.py",
        "app/core/integrity_check.py",
        "app/routes/dashboard.py",
        "tests/",
    ],
    "upload": [
        "app/core/upload_pipeline.py",
        "app/core/ocr_corrector.py",
        "app/core/rag_sync.py",
        "app/templates/review.html",
        "app/templates/dashboard.html",
    ],
    "emailpostfach": [
        "app/mail/",
        "app/agents/mail.py",
        "app/plugins/mail.py",
        "app/templates/messenger.html",
    ],
    "messenger": [
        "app/agents/orchestrator.py",
        "app/agents/planner.py",
        "app/agents/memory_store.py",
        "app/templates/messenger.html",
    ],
    "kalender": [
        "app/knowledge/ics_source.py",
        "app/knowledge/core.py",
        "app/templates/generic_tool.html",
    ],
    "aufgaben": [
        "app/modules/projects/logic.py",
        "app/modules/automation/",
        "app/templates/kanban.html",
    ],
    "zeiterfassung": [
        "app/templates/generic_tool.html",
        "app/modules/projects/logic.py",
    ],
    "projekte": [
        "app/modules/projects/",
        "app/templates/kanban.html",
    ],
    "excel-docs-visualizer": [
        "app/templates/visualizer.html",
        "app/static/js/",
    ],
    "einstellungen": [
        "app/core/tenant_registry.py",
        "app/core/mesh_network.py",
        "app/license.py",
        "app/routes/admin_tenants.py",
        "app/templates/settings.html",
    ],
    "floating-widget-chatbot": [
        "app/templates/partials/floating_chat.html",
        "app/static/js/chatbot.js",
    ],
}


def _detect_repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip())
    return Path(__file__).resolve().parents[2]


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _rel(repo_root: Path, path: str) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(repo_root)).replace("\\", "/")
        except Exception:
            return str(p).replace("\\", "/")
    return str(p).replace("\\", "/").lstrip("./")


def _matches_allowlist(rel_path: str, allowlist: list[str]) -> bool:
    for rule in allowlist:
        rule = rule.replace("\\", "/")
        if rule.endswith("/"):
            if rel_path.startswith(rule):
                return True
        elif rel_path == rule:
            return True
    return False


def _is_ignored_path(rel_path: str) -> bool:
    return any(rel_path.startswith(prefix) for prefix in GLOBAL_IGNORES)


def _branch_file_set(repo_root: Path, branch: str, base_branch: str) -> set[str]:
    base_ref = _run_git(repo_root, ["rev-parse", "--verify", base_branch])
    if not base_ref:
        return set()
    merge_base = _run_git(repo_root, ["merge-base", branch, base_branch])
    if not merge_base:
        return set()
    out = _run_git(repo_root, ["diff", "--name-only", f"{merge_base}..{branch}"])
    return {line.strip() for line in out.splitlines() if line.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect cross-domain overlaps for tab projects")
    parser.add_argument("--reiter", required=True, choices=sorted(ALLOWLIST.keys()))
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--base-branch", default="main")
    parser.add_argument(
        "--include-branch-overlaps",
        action="store_true",
        help="Treat overlaps with other local codex/* branches as hard failures",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = _detect_repo_root()
    files = sorted({_rel(repo_root, f) for f in args.files if f and not _is_ignored_path(_rel(repo_root, f))})
    allowlist = ALLOWLIST[args.reiter]

    outside_allowlist = [f for f in files if not _matches_allowlist(f, allowlist)]
    shared_core_touched = sorted(
        [
            f
            for f in files
            if (f in SHARED_CORE or any(f.startswith(prefix) for prefix in SHARED_CORE_PREFIXES))
            and not _matches_allowlist(f, allowlist)
        ]
    )

    branch_overlaps: dict[str, list[str]] = {}
    current_branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]) or ""
    if args.include_branch_overlaps:
        codex_branches_raw = _run_git(
            repo_root,
            ["for-each-ref", "--format=%(refname:short)", "refs/heads/codex/"],
        )
        codex_branches = [b for b in codex_branches_raw.splitlines() if b and b != current_branch]
        for branch in codex_branches:
            changed = _branch_file_set(repo_root, branch, args.base_branch)
            overlap = sorted([f for f in files if f in changed])
            if overlap:
                branch_overlaps[branch] = overlap

    has_overlap = bool(
        outside_allowlist
        or shared_core_touched
        or (args.include_branch_overlaps and branch_overlaps)
    )

    result = {
        "status": "DOMAIN_OVERLAP_DETECTED" if has_overlap else "OK",
        "reiter": args.reiter,
        "current_branch": current_branch,
        "files": files,
        "outside_allowlist": outside_allowlist,
        "shared_core_touched": shared_core_touched,
        "branch_overlaps": branch_overlaps,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']}")
        print(f"reiter={args.reiter}")
        if outside_allowlist:
            print("outside_allowlist:")
            for f in outside_allowlist:
                print(f"  - {f}")
        if shared_core_touched:
            print("shared_core_touched:")
            for f in shared_core_touched:
                print(f"  - {f}")
        if branch_overlaps:
            print("branch_overlaps:")
            for b, overlap in sorted(branch_overlaps.items()):
                print(f"  - {b}")
                for f in overlap:
                    print(f"    * {f}")

    return 2 if has_overlap else 0


if __name__ == "__main__":
    raise SystemExit(main())
