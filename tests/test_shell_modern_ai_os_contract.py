from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_topbar_exposes_command_palette_trigger_and_shortcut() -> None:
    html = _read("app/templates/partials/topbar.html")

    assert 'id="topbar-search-trigger"' in html
    assert "Command Palette öffnen" in html
    assert "topbar-search-placeholder" in html
    assert "topbar-shortcut" in html
    assert "⌘K" in html


def test_topbar_keeps_white_mode_chip_visible_in_shell() -> None:
    html = _read("app/templates/partials/topbar.html")

    assert 'class="mode-chip"' in html
    assert "White Mode" in html


def test_sidebar_contains_workspace_core_communication_and_system_sections() -> None:
    html = _read("app/templates/partials/sidebar.html")

    assert "sidebar-workspace" in html
    assert "Core" in html
    assert "Kommunikation" in html
    assert "System" in html
    assert "Assistenz" in html


def test_sidebar_uses_sprite_icons_and_data_route_metadata() -> None:
    html = _read("app/templates/partials/sidebar.html")

    assert "icon-dashboard" in html
    assert "icon-projects" in html
    assert "icon-assistant" in html
    assert "/static/icons/sprite.svg#{{ item.icon }}" in html
    assert "data-route=" in html
    assert "data-nav-key=" in html


def test_command_palette_registers_keyboard_shortcut_navigation_and_overlay() -> None:
    js = _read("app/static/js/command_palette.js")

    assert "(event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k'" in js
    assert "cmd-palette-overlay" in js
    assert "cmdk-overlay" in js
    assert "this.renderResults();" in js
    assert "this.execute(this.filtered[this.selectedIndex]);" in js


def test_command_palette_includes_required_primary_commands() -> None:
    js = _read("app/static/js/command_palette.js")

    assert "nav-dash" in js
    assert "nav-projects" in js
    assert "nav-tasks" in js
    assert "nav-upload" in js
    assert "nav-messenger" in js
    assert "nav-assistant" in js
    assert "nav-settings" in js


def test_shell_css_defines_command_palette_modal_and_mobile_shell_rules() -> None:
    css = _read("app/static/css/shell-navigation.css")

    assert ".cmdk-overlay" in css
    assert ".cmdk-modal" in css
    assert ".cmdk-header" in css
    assert ".cmdk-list" in css
    assert ".mobile-sidebar-overlay" in css
    assert "@media (max-width: 768px)" in css
    assert ".mobile-bottom-nav" in css


def test_shell_css_keeps_sidebar_and_topbar_foundation_rules() -> None:
    css = _read("app/static/css/shell-navigation.css")

    assert ".sidebar {" in css
    assert ".sidebar-header" in css
    assert ".sidebar-workspace" in css
    assert ".topbar {" in css
    assert ".topbar-leading" in css
    assert ".topbar-actions" in css
