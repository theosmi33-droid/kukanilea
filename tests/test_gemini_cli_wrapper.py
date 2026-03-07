from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ai" / "gemini_cli.py"
SPEC = importlib.util.spec_from_file_location("gemini_cli", MODULE_PATH)
assert SPEC and SPEC.loader
GEMINI_CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEMINI_CLI)


def test_resolve_approval_mode_requires_explicit_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_APPROVAL_MODE", raising=False)
    with pytest.raises(ValueError, match="missing explicit approval mode"):
        GEMINI_CLI.resolve_approval_mode(None)


def test_resolve_approval_mode_accepts_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_APPROVAL_MODE", "default")
    assert GEMINI_CLI.resolve_approval_mode(None) == "default"


def test_main_rejects_empty_sanitized_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        GEMINI_CLI,
        "parse_args",
        lambda: type(
            "Args",
            (),
                {
                    "prompt": "x",
                    "prompt_file": None,
                    "domain": None,
                    "context_file": [],
                "output": None,
                "log": None,
                "cwd": None,
                    "approval_mode": "default",
                    "raw": False,
                    "timeout_seconds": 1,
                    "model": None,
                    "extension": [],
                    "require_main": False,
                    "skip_alignment": False,
                },
            )(),
        )
    monkeypatch.setattr(
        GEMINI_CLI,
        "run_gemini",
        lambda prompt, approval_mode, model, extensions, cwd, timeout_seconds: (0, "YOLO mode is enabled.\n"),
    )

    rc = GEMINI_CLI.main()

    captured = capsys.readouterr()
    assert rc == 1
    assert "empty output after sanitization" in captured.err
