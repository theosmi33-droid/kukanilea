from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRECISE_LAUNCHER = ROOT / "scripts" / "ai" / "runtime" / "start_4terminals_precise.sh"
INTERACTIVE_LAUNCHER = ROOT / "scripts" / "ai" / "runtime" / "start_gemini_main_only_interactive.sh"


def test_precise_launcher_uses_argv_based_osascript_bridge() -> None:
    content = PRECISE_LAUNCHER.read_text(encoding="utf-8")
    assert 'osascript - "$cmd" <<\'APPLESCRIPT\'' in content
    assert "on run argv" in content
    assert "do script commandText" in content
    assert "do script \"clear; export GEMINI_MODEL='" not in content


def test_interactive_launcher_blocks_non_main_without_checkout_side_effect() -> None:
    content = INTERACTIVE_LAUNCHER.read_text(encoding="utf-8")
    assert "main-only policy active" in content
    assert "git checkout main" not in content
    assert "working tree has local changes" in content
