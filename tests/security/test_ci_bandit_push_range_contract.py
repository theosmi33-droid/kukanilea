from __future__ import annotations

from pathlib import Path

CI_WORKFLOW = Path(".github/workflows/ci.yml")


def test_ci_bandit_push_mode_reads_event_before_sha_without_heredoc() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "python -c 'import json, os; from pathlib import Path" in text
    assert 'os.environ.get("GITHUB_EVENT_PATH", "")' in text
    assert "before_sha=\"$(python - <<'PY'" not in text


def test_ci_bandit_push_mode_keeps_safe_fallbacks() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert 'git diff --name-only "${before_sha}...HEAD" -- \'*.py\' \':!app/static/**\'' in text
    assert "Could not resolve before SHA; scanning all tracked Python files as a safe fallback." in text
    assert "mapfile -t py_targets < <(git ls-files '*.py' ':!app/static/**')" in text
