import json
import re
from pathlib import Path


def _extract_root_tokens(css_text: str) -> dict[str, str]:
    root_section = css_text.split("/* Task 152: Ripple Effect */", 1)[0]
    tokens: dict[str, str] = {}
    for line in root_section.splitlines():
        line = line.strip()
        if line.startswith("--") and ":" in line:
            name, value = line.split(":", 1)
            tokens[name.strip()] = value.strip().rstrip(";")
    return tokens


def test_white_mode_design_tokens_snapshot():
    css_text = Path("app/static/css/design-system.css").read_text(encoding="utf-8")
    actual_tokens = _extract_root_tokens(css_text)
    expected_tokens = json.loads(
        Path("tests/snapshots/design_system_white_mode_tokens.json").read_text(encoding="utf-8")
    )
    assert actual_tokens == expected_tokens


def test_white_mode_hardening_actions_snapshot_contract():
    actions = json.loads(Path("tests/snapshots/white_mode_hardening_actions.json").read_text(encoding="utf-8"))
    assert len(actions) >= 2300
    assert all(action["scope"] == "white-mode" and action["status"] == "applied" for action in actions)


def test_no_dark_mode_overrides_in_system_css():
    css_text = Path("app/static/css/system.css").read_text(encoding="utf-8")
    assert "@media (prefers-color-scheme: dark)" not in css_text
    assert re.search(r"#0f1115|rgba\(15,\s*17,\s*21", css_text) is None
