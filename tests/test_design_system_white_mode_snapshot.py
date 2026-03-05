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
    css_text = Path("app/static/css/design-system.css").read_text(encoding="utf-8")
    declared_tokens = set(re.findall(r"(--[a-z0-9-]+)\s*:", css_text))

    required_tokens = {
        "--bg-primary",
        "--text-primary",
        "--color-bg-root",
        "--color-bg-panel",
        "--color-text-main",
        "--color-accent",
        "--color-danger",
        "--border-color",
        "--spacing-1",
        "--spacing-2",
        "--shadow-sm",
        "--shadow-md",
        "--radius-md",
        "--transition-base",
    }
    assert required_tokens.issubset(declared_tokens)

    color_tokens = [token for token in declared_tokens if token.startswith("--color-")]
    spacing_tokens = [token for token in declared_tokens if token.startswith("--spacing-")]
    shadow_tokens = [token for token in declared_tokens if token.startswith("--shadow-")]
    radius_tokens = [token for token in declared_tokens if token.startswith("--radius-")]
    assert len(color_tokens) >= 18
    assert len(spacing_tokens) >= 8
    assert len(shadow_tokens) >= 5
    assert len(radius_tokens) >= 4

    assert "color-scheme: light;" in css_text
    assert "@media (prefers-color-scheme: dark)" not in css_text


def test_no_dark_mode_overrides_in_system_css():
    css_text = Path("app/static/css/system.css").read_text(encoding="utf-8")
    assert "@media (prefers-color-scheme: dark)" not in css_text
    assert re.search(r"#0f1115|rgba\(15,\s*17,\s*21", css_text) is None
