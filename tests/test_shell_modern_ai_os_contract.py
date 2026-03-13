from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_topbar_omits_command_palette_trigger_and_system_chrome() -> None:
    html = _read("app/templates/partials/topbar.html")

    assert 'id="topbar-search-trigger"' not in html
    assert "Command Palette öffnen" not in html
    assert "topbar-search-placeholder" not in html
    assert "topbar-shortcut" not in html
    assert "components/system_status.html" not in html
    assert 'class="mode-chip"' not in html
    assert "White Mode" not in html
    assert 'id="sidebar-toggle-top"' not in html
    assert 'id="mobile-sidebar-toggle"' not in html
    assert 'id="topbar-clock"' in html
    assert 'id="topbar-online-count"' in html
    assert 'id="topbar-running-timer"' in html
    assert 'id="topbar-time-hide"' in html
    assert 'id="topbar-workspace-id"' in html
    assert 'id="topbar-notifications"' in html
    assert "topbar-workspace-meta" in html
    assert "topbar-notification" in html
    assert "topbar-account" in html
    assert html.index('id="topbar-workspace-id"') < html.index('id="topbar-clock"')
    assert html.index('id="topbar-clock"') < html.index('id="topbar-online-count"')
    assert html.index('id="topbar-online-count"') < html.index('id="topbar-running-timer"')
    assert html.index('id="topbar-running-timer"') < html.index('id="topbar-notifications"')
    assert html.index('id="topbar-notifications"') < html.index("topbar-account")


def test_sidebar_contains_workspace_and_primary_navigation_entries() -> None:
    html = _read("app/templates/partials/sidebar.html")

    assert "sidebar-workspace" not in html
    assert "sidebar-user" not in html
    assert ">Navigation<" not in html
    assert "sidebar-disclosure-icon" in html
    for nav_key in [
        "dashboard",
        "upload",
        "email",
        "messenger",
        "calendar",
        "tasks",
        "time",
        "projects",
        "visualizer",
        "settings",
        "assistant",
    ]:
        if nav_key == "assistant":
            assert 'data-nav-key="assistant"' in html
            continue
        assert f"'key': '{nav_key}'" in html


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
    assert ".topbar-right" in css
    assert ".topbar-actions" in css
    assert "html.sidebar-collapsed .sidebar .nav-text" in css
    assert ".sidebar-disclosure-icon" in css
