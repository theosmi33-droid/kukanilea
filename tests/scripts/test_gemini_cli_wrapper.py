from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ai" / "gemini_cli.py"
    spec = importlib.util.spec_from_file_location("kukanilea_gemini_cli", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_prompt_respects_skip_alignment(tmp_path: Path) -> None:
    mod = _load_module()
    root = tmp_path
    alignment = root / "docs" / "ai" / "GEMINI_ALIGNMENT_PROMPT.md"
    alignment.parent.mkdir(parents=True, exist_ok=True)
    alignment.write_text("ALIGNMENT", encoding="utf-8")

    prompt_skip = mod.build_prompt(root, "task body", None, [], skip_alignment=True)
    assert "ALIGNMENT" not in prompt_skip
    assert "task body" in prompt_skip

    prompt_full = mod.build_prompt(root, "task body", None, [], skip_alignment=False)
    assert "ALIGNMENT" in prompt_full
    assert "task body" in prompt_full


def test_enforce_main_branch_accepts_main(tmp_path: Path) -> None:
    mod = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True, text=True)

    ok, message = mod.enforce_main_branch(repo, repo)
    assert ok is True
    assert message == ""


def test_enforce_main_branch_rejects_non_main(tmp_path: Path) -> None:
    mod = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "checkout", "-b", "feature/demo"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True, text=True)

    ok, message = mod.enforce_main_branch(repo, repo)
    assert ok is False
    assert "main-only policy active" in message
    assert "feature/demo" in message
