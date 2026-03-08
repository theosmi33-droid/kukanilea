#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FailureRun:
    database_id: int
    workflow_name: str
    head_branch: str
    display_title: str
    created_at: str
    url: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FailureRun":
        return cls(
            database_id=int(payload.get("databaseId") or 0),
            workflow_name=str(payload.get("workflowName") or ""),
            head_branch=str(payload.get("headBranch") or ""),
            display_title=str(payload.get("displayTitle") or ""),
            created_at=str(payload.get("createdAt") or ""),
            url=str(payload.get("url") or ""),
        )


def _run_json(cmd: list[str]) -> Any:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(proc.stdout)


def fetch_failed_runs(repo: str, limit: int) -> list[FailureRun]:
    payload = _run_json(
        [
            "gh",
            "run",
            "list",
            "-R",
            repo,
            "--status",
            "failure",
            "--limit",
            str(limit),
            "--json",
            "databaseId,workflowName,headBranch,displayTitle,createdAt,url",
        ]
    )
    return [FailureRun.from_payload(item) for item in payload]


def fetch_open_pr_head_branches(repo: str, limit: int = 200) -> list[str]:
    payload = _run_json(
        [
            "gh",
            "pr",
            "list",
            "-R",
            repo,
            "--state",
            "open",
            "--limit",
            str(limit),
            "--json",
            "headRefName",
        ]
    )
    branches: list[str] = []
    for row in payload:
        name = str(row.get("headRefName") or "").strip()
        if name:
            branches.append(name)
    return branches


def build_allowed_branches(open_pr_heads: list[str]) -> set[str]:
    allowed = {"main"}
    for branch in open_pr_heads:
        branch = branch.strip()
        if branch:
            allowed.add(branch)
    return allowed


def filter_actionable_failures(failures: list[FailureRun], allowed_branches: set[str]) -> list[FailureRun]:
    return [run for run in failures if run.head_branch in allowed_branches]


def format_runs(runs: list[FailureRun]) -> list[str]:
    return [
        f"- [{run.head_branch}] {run.workflow_name} | {run.display_title} | {run.created_at} | {run.url}"
        for run in runs
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List actionable GitHub Actions failures.")
    parser.add_argument("--repo", default="theosmi33-droid/kukanilea")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--all", action="store_true", help="Show all failed runs instead of actionable scope.")
    parser.add_argument("--failed-runs-json", help="Path to JSON payload for failed runs (test/offline mode).")
    parser.add_argument("--open-prs-json", help="Path to JSON payload for open PR heads (test/offline mode).")
    return parser.parse_args(argv)


def _load_failed_runs(path: str) -> list[FailureRun]:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return [FailureRun.from_payload(item) for item in payload]


def _load_open_pr_branches(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    branches: list[str] = []
    for row in payload:
        name = str(row.get("headRefName") or "").strip()
        if name:
            branches.append(name)
    return branches


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.failed_runs_json:
        failures = _load_failed_runs(args.failed_runs_json)
    else:
        failures = fetch_failed_runs(args.repo, args.limit)

    if args.all:
        if not failures:
            print("No failed runs found.")
            return 0
        for line in format_runs(failures):
            print(line)
        return 0

    if args.open_prs_json:
        open_pr_heads = _load_open_pr_branches(args.open_prs_json)
    else:
        open_pr_heads = fetch_open_pr_head_branches(args.repo)

    allowed = build_allowed_branches(open_pr_heads)
    actionable = filter_actionable_failures(failures, allowed)

    print(f"Repo: {args.repo}")
    print(f"Window: last {args.limit} failed runs")
    print(f"Total failed runs: {len(failures)}")
    print(f"Actionable failed runs (main + open PR branches): {len(actionable)}")
    print()

    if not actionable:
        print("No actionable failures.")
        return 0

    for line in format_runs(actionable):
        print(line)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as exc:
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return_code = exc.returncode or 1
        raise SystemExit(return_code)
