from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_policy_drift_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts/ops/policy_drift_audit.py"
    module_name = "policy_drift_audit"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_scope_error_is_treated_as_drift_and_fails(tmp_path: Path, monkeypatch, capsys) -> None:
    audit = _load_policy_drift_module()
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"branches": {"main": {}}}), encoding="utf-8")

    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("POLICY_AUDIT_TOKEN", "token")
    monkeypatch.setenv("POLICY_BASELINE_PATH", str(baseline_path))

    calls = {"created": 0, "body": ""}

    class FakeGitHubAPI:
        def __init__(self, token: str, repo: str) -> None:
            assert token == "token"
            assert repo == "owner/repo"

        def get_branch_protection(self, branch: str) -> dict:
            raise RuntimeError(
                "GitHub API GET repos/owner/repo/branches/main/protection failed: "
                "403 {\"message\":\"Resource not accessible by integration\"}"
            )

        def list_open_issues(self) -> list[dict]:
            return []

        def create_issue(self, title: str, body: str) -> dict:
            calls["created"] += 1
            calls["body"] = body
            return {"number": 42, "title": title}

        def create_comment(self, issue_number: int, body: str) -> dict:
            raise AssertionError(f"unexpected comment call for issue {issue_number}")

    monkeypatch.setattr(audit, "GitHubAPI", FakeGitHubAPI)

    rc = audit.main()
    output = capsys.readouterr().out

    assert rc == 2
    assert calls["created"] == 1
    assert "protection_api_scope" in calls["body"]
    assert "Skipped branch protection audit for: main" in output
    assert "No policy drift detected" not in output
