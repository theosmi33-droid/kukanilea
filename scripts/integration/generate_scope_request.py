#!/usr/bin/env python3
"""Generate a scope-request markdown + patch for shared-core changes.

Usage:
  python scripts/integration/generate_scope_request.py --domain dashboard
  python scripts/integration/generate_scope_request.py --domain dashboard --auto-revert
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SHARED_CORE_FILES = [
    "app/web.py",
    "app/db.py",
    "app/core/logic.py",
    "app/__init__.py",
    "app/templates/layout.html",
    "app/templates/partials/*",
    "app/static/css/components.css",
    "app/static/fonts/*",
    "app/static/icons/*",
    "app/static/js/vendor/htmx.min.js",
]


@dataclass
class ScopeArtifacts:
    scope_md: Path
    patch_file: Path
    shared_files: list[str]


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def detect_repo_root() -> Path:
    cp = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode == 0 and cp.stdout.strip():
        return Path(cp.stdout.strip())
    return Path(__file__).resolve().parents[2]


def git_changed_files(repo_root: Path, base_branch: str) -> list[str]:
    cp = run(["git", "diff", "--name-only", base_branch, "--"], repo_root)
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def match_shared(files: list[str]) -> list[str]:
    out: list[str] = []
    for f in files:
        if any(fnmatch.fnmatch(f, pattern) for pattern in SHARED_CORE_FILES):
            out.append(f)
    return sorted(set(out))


def render_files_changed(files: list[str]) -> str:
    if not files:
        return "- None"
    return "\n".join(f"- {f}" for f in files)


def generate_patch_file(repo_root: Path, base_branch: str, files: list[str], patch_file: Path) -> None:
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    if not files:
        patch_file.write_text("")
        return

    cmd = ["git", "diff", "--binary", base_branch, "--", *files]
    cp = run(cmd, repo_root)
    patch_file.write_text(cp.stdout)


def load_template(path: Path) -> str:
    if path.exists():
        return path.read_text()
    fallback = Path(__file__).resolve().parents[2] / "docs/templates/SCOPE_REQUEST_TEMPLATE.md"
    if fallback.exists():
        return fallback.read_text()
    raise FileNotFoundError(f"Template not found: {path}")


def write_scope_request(
    template: str,
    scope_file: Path,
    domain: str,
    date_str: str,
    patch_file: Path,
    files_changed: list[str],
) -> None:
    filled = template.format(
        domain=domain,
        date=date_str,
        patch_file=str(patch_file).replace("\\", "/"),
        files_changed=render_files_changed(files_changed),
    )
    scope_file.parent.mkdir(parents=True, exist_ok=True)
    scope_file.write_text(filled)


def auto_revert(repo_root: Path, files: list[str]) -> None:
    if not files:
        return
    run(["git", "checkout", "--", *files], repo_root)


def build_artifacts(args: argparse.Namespace, repo_root: Path) -> ScopeArtifacts:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scope_md = (
        repo_root
        / args.output_dir
        / f"{args.domain}_{stamp}.md"
    )
    patch_file = (
        repo_root
        / args.patch_dir
        / f"{args.domain}_{stamp}.patch"
    )

    changed = git_changed_files(repo_root, args.base_branch)
    shared = match_shared(changed)

    if args.dry_run:
        print("[dry-run] changed files:")
        for f in changed:
            print(f"  - {f}")
        print("[dry-run] shared-core matches:")
        for f in shared:
            print(f"  - {f}")
        return ScopeArtifacts(scope_md=scope_md, patch_file=patch_file, shared_files=shared)

    template = load_template(repo_root / args.template)
    generate_patch_file(repo_root, args.base_branch, shared, patch_file)
    write_scope_request(
        template=template,
        scope_file=scope_md,
        domain=args.domain,
        date_str=datetime.now().date().isoformat(),
        patch_file=patch_file,
        files_changed=shared,
    )

    if args.auto_revert:
        auto_revert(repo_root, shared)

    return ScopeArtifacts(scope_md=scope_md, patch_file=patch_file, shared_files=shared)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate shared-core scope-request artifacts")
    parser.add_argument("--domain", required=True, help="Domain/worktree name, e.g. dashboard")
    parser.add_argument("--base-branch", default="main", help="Git base ref for diff (default: main)")
    parser.add_argument(
        "--template",
        default="docs/templates/SCOPE_REQUEST_TEMPLATE.md",
        help="Template path relative to repo root",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/scope_requests",
        help="Output directory for markdown scope requests",
    )
    parser.add_argument(
        "--patch-dir",
        default="docs/scope_requests/patches",
        help="Output directory for patch files",
    )
    parser.add_argument("--auto-revert", action="store_true", help="Revert matched shared-core files after extraction")
    parser.add_argument("--dry-run", action="store_true", help="Preview matched files without writing artifacts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = detect_repo_root()

    try:
        artifacts = build_artifacts(args, repo_root)
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or exc.stdout, file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        return 0

    print(f"scope_request={artifacts.scope_md}")
    print(f"patch_file={artifacts.patch_file}")
    if artifacts.shared_files:
        print("shared_files=")
        for f in artifacts.shared_files:
            print(f"  - {f}")
    else:
        print("shared_files=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
