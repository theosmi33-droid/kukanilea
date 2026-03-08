from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRECISE_LAUNCHER = ROOT / "scripts" / "ai" / "runtime" / "start_4terminals_precise.sh"
INTERACTIVE_LAUNCHER = ROOT / "scripts" / "ai" / "runtime" / "start_gemini_main_only_interactive.sh"
STAGGERED_LAUNCHER = ROOT / "scripts" / "ai" / "runtime" / "start_4terminals_staggered.sh"
PRECISE_RUNNER = ROOT / "scripts" / "ai" / "runtime" / "run_gemini_precise.sh"
MAIN_ONLY_LIB = ROOT / "scripts" / "ai" / "runtime" / "lib_main_only.sh"


def test_precise_launcher_uses_argv_based_osascript_bridge() -> None:
    content = PRECISE_LAUNCHER.read_text(encoding="utf-8")
    assert 'osascript - "$cmd" <<\'APPLESCRIPT\'' in content
    assert "on run argv" in content
    assert "do script commandText" in content
    assert "do script \"clear; export GEMINI_MODEL='" not in content


def test_interactive_launcher_blocks_non_main_without_checkout_side_effect() -> None:
    content = INTERACTIVE_LAUNCHER.read_text(encoding="utf-8")
    assert "source \"$ROOT/scripts/ai/runtime/lib_main_only.sh\"" in content
    assert "main_only_preflight" in content
    assert "git checkout main" not in content


def test_staggered_launcher_enforces_clean_main_preflight() -> None:
    content = STAGGERED_LAUNCHER.read_text(encoding="utf-8")
    assert "source \"$ROOT/scripts/ai/runtime/lib_main_only.sh\"" in content
    assert "main_only_preflight" in content
    assert "start_4terminals_precise.sh" in content


def test_precise_runner_validates_runtime_inputs() -> None:
    content = PRECISE_RUNNER.read_text(encoding="utf-8")
    assert "GEMINI_TIMEOUT_SECONDS must be numeric" in content
    assert "GEMINI_APPROVAL_MODE must be 'default' or 'yolo'" in content
    assert "invalid extension token" in content


def test_main_only_lib_enforces_branch_clean_and_sync() -> None:
    content = MAIN_ONLY_LIB.read_text(encoding="utf-8")
    assert "main-only policy active" in content
    assert "working tree has local changes" in content
    assert "local main not synced with origin/main" in content


def test_precise_launcher_uses_main_only_preflight_lib() -> None:
    content = PRECISE_LAUNCHER.read_text(encoding="utf-8")
    assert "source \"$ROOT/scripts/ai/runtime/lib_main_only.sh\"" in content
    assert "main_only_preflight" in content
