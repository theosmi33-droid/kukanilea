#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ISSUE_TITLE = "Policy Drift Detected (Branch Protection)"


@dataclass
class Drift:
    branch: str
    field: str
    expected: Any
    actual: Any


class GitHubAPI:
    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo
        self.base = "https://api.github.com"

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base}/{path.lstrip('/')}"
        body = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "kukanilea-policy-audit",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, method=method, headers=headers, data=body)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
                if not data:
                    return None
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc

    def get_branch_protection(self, branch: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(branch, safe="")
        return self.request("GET", f"repos/{self.repo}/branches/{encoded}/protection")

    def list_open_issues(self) -> list[dict[str, Any]]:
        return self.request("GET", f"repos/{self.repo}/issues?state=open&per_page=100")

    def create_issue(self, title: str, body: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"repos/{self.repo}/issues",
            {"title": title, "body": body},
        )

    def create_comment(self, issue_number: int, body: str) -> dict[str, Any]:
        return self.request(
            "POST",
            f"repos/{self.repo}/issues/{issue_number}/comments",
            {"body": body},
        )


def normalize_protection(raw: dict[str, Any]) -> dict[str, Any]:
    checks = [c["context"] for c in raw["required_status_checks"]["checks"]]
    return {
        "required_approving_review_count": raw["required_pull_request_reviews"][
            "required_approving_review_count"
        ],
        "require_code_owner_reviews": raw["required_pull_request_reviews"][
            "require_code_owner_reviews"
        ],
        "dismiss_stale_reviews": raw["required_pull_request_reviews"][
            "dismiss_stale_reviews"
        ],
        "required_conversation_resolution": raw["required_conversation_resolution"][
            "enabled"
        ],
        "required_status_checks_strict": raw["required_status_checks"]["strict"],
        "required_status_checks": checks,
        "enforce_admins": raw["enforce_admins"]["enabled"],
        "allow_force_pushes": raw["allow_force_pushes"]["enabled"],
        "allow_deletions": raw["allow_deletions"]["enabled"],
        "block_creations": raw["block_creations"]["enabled"],
        "lock_branch": raw["lock_branch"]["enabled"],
        "allow_fork_syncing": raw["allow_fork_syncing"]["enabled"],
    }


def compare(expected: dict[str, Any], actual: dict[str, Any], branch: str) -> list[Drift]:
    drifts: list[Drift] = []
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        if field == "required_status_checks":
            if sorted(expected_value) != sorted(actual_value or []):
                drifts.append(Drift(branch, field, sorted(expected_value), sorted(actual_value or [])))
        elif expected_value != actual_value:
            drifts.append(Drift(branch, field, expected_value, actual_value))
    return drifts


def render_issue_body(repo: str, baseline_path: Path, drifts: list[Drift]) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        "## Branch Protection Drift Detected",
        "",
        f"- Repository: `{repo}`",
        f"- Baseline: `{baseline_path}`",
        f"- Timestamp (UTC): `{ts}`",
        "",
        "### Drift Details",
        "",
        "| Branch | Field | Expected | Actual |",
        "|---|---|---|---|",
    ]
    for drift in drifts:
        lines.append(
            f"| `{drift.branch}` | `{drift.field}` | `{json.dumps(drift.expected)}` | `{json.dumps(drift.actual)}` |"
        )

    lines.extend(
        [
            "",
            "### Immediate Actions",
            "1. Verify whether change was intentional (release emergency or admin override).",
            "2. Restore protection to baseline if unintentional.",
            "3. Re-run workflow `Policy Drift Audit` to confirm clean state.",
        ]
    )
    return "\n".join(lines)


def upsert_drift_issue(api: GitHubAPI, body: str) -> None:
    open_issues = api.list_open_issues()
    existing = next(
        (
            issue
            for issue in open_issues
            if issue.get("title") == ISSUE_TITLE and "pull_request" not in issue
        ),
        None,
    )

    if existing is None:
        created = api.create_issue(ISSUE_TITLE, body)
        print(f"Created drift issue #{created['number']}")
        return

    api.create_comment(existing["number"], body)
    print(f"Updated drift issue #{existing['number']}")


def load_baseline(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    branches = data.get("branches")
    if not isinstance(branches, dict) or not branches:
        raise ValueError("Baseline JSON must contain non-empty 'branches' map")
    return branches


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "theosmi33-droid/kukanilea")
    token = os.getenv("GITHUB_TOKEN")
    baseline_path = Path(
        os.getenv(
            "POLICY_BASELINE_PATH",
            ".github/policy/branch_protection_baseline.json",
        )
    )

    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 1
    if not baseline_path.exists():
        print(f"Baseline file missing: {baseline_path}", file=sys.stderr)
        return 1

    branches = load_baseline(baseline_path)
    api = GitHubAPI(token=token, repo=repo)

    drifts: list[Drift] = []
    for branch, expected in branches.items():
        try:
            actual_raw = api.get_branch_protection(branch)
        except RuntimeError as exc:
            drifts.append(Drift(branch, "protection_api", "available", str(exc)))
            continue

        actual = normalize_protection(actual_raw)
        drifts.extend(compare(expected, actual, branch))

    if not drifts:
        print("No policy drift detected")
        return 0

    issue_body = render_issue_body(repo, baseline_path, drifts)
    upsert_drift_issue(api, issue_body)
    print(f"Policy drift found: {len(drifts)} differences")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
