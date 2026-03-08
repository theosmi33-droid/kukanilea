from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_command_palette_includes_core_navigation_targets() -> None:
    js = _read("static/js/command_palette.js")
    assert "id: 'nav-dashboard'" in js
    assert "id: 'nav-systems'" in js
    assert "id: 'nav-agents'" in js
    assert "id: 'nav-files'" in js
    assert "id: 'nav-automation'" in js
    assert "id: 'nav-settings'" in js


def test_command_palette_uses_supported_logs_route() -> None:
    js = _read("static/js/command_palette.js")
    assert "window.location.href = '/system/logs';" in js
    assert "/system-logs" not in js


def test_command_palette_supports_keyboard_navigation_contract() -> None:
    js = _read("static/js/command_palette.js")
    assert "(e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k'" in js
    assert "e.key === 'Escape'" in js
    assert "e.key === 'ArrowDown'" in js
    assert "e.key === 'ArrowUp'" in js
    assert "e.key === 'Enter'" in js
    assert "activateSelection()" in js


def test_layout_shell_marks_current_nav_and_mobile_routes() -> None:
    js = _read("static/js/layout-shell.js")
    assert "document.querySelectorAll('.nav-link[data-route]')" in js
    assert "document.querySelectorAll('.mobile-nav-item[data-route]')" in js
    assert "aria-current" in js


def test_shell_navigation_css_contains_new_layout_regions() -> None:
    css = _read("static/css/shell-navigation.css")
    required = [
        ".sidebar",
        ".topbar-main-row",
        ".context-panels",
        ".context-panel",
        ".mobile-bottom-nav",
        ".mobile-nav-item",
    ]
    for token in required:
        assert token in css
