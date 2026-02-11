from __future__ import annotations

import test_conflict_markers as conflict_markers


def test_inside_git_repo_false_when_not_git(monkeypatch) -> None:
    class Result:
        returncode = 128
        stdout = ""

    monkeypatch.setattr(conflict_markers.subprocess, "run", lambda *a, **k: Result())
    assert conflict_markers._inside_git_repo() is False
