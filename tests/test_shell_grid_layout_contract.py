from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_layout_defines_shell_grid_main_and_context_regions() -> None:
    html = _read("app/templates/layout.html")
    assert 'class="app-shell"' in html
    assert 'class="shell-grid"' in html
    assert '<main class="main-content" id="app-main"' in html
    assert '<aside class="context-panel" id="context-panel"' in html
    assert 'aria-labelledby="main-content-heading"' in html


def test_layout_keeps_mobile_bottom_nav_and_topbar_in_shell() -> None:
    html = _read("app/templates/layout.html")
    assert "{% include 'partials/topbar.html' %}" in html
    assert 'class="mobile-bottom-nav"' in html
    assert 'data-route="/dashboard"' in html
    assert 'data-route="/projects"' in html
    assert 'data-route="/tasks"' in html
    assert 'data-route="/messenger"' in html


def test_shell_navigation_css_contains_grid_and_context_rules() -> None:
    css = _read("app/static/css/shell-navigation.css")
    expected_rules = [
        ".sidebar",
        ".nav-link.active::before",
        ".topbar",
        ".topbar-search-container",
        ".mobile-sidebar-overlay",
    ]
    for rule in expected_rules:
        assert rule in css


def test_shell_navigation_css_contains_responsive_mobile_rules() -> None:
    css = _read("app/static/css/shell-navigation.css")
    assert "@media (max-width: 768px)" in css
    assert ".sidebar" in css
    assert ".mobile-bottom-nav" in css
    assert "padding-bottom: calc(84px + env(safe-area-inset-bottom, 0px))" in css


def test_shell_navigation_css_keeps_sidebar_collapse_contract() -> None:
    css = _read("app/static/css/shell-navigation.css")
    assert ".sidebar" in css
    assert ".nav-link" in css
    assert ".nav-link.active::before" in css
