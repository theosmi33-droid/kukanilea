from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_login_template_loads_system_and_components_stylesheets() -> None:
    html = _read("app/templates/login.html")
    assert '<link rel="stylesheet" href="/static/css/system.css">' in html
    assert '<link rel="stylesheet" href="/static/css/components.css">' in html
    assert "Sicher anmelden und direkt weiterarbeiten." in html


def test_components_css_defines_panel_button_and_input_contracts() -> None:
    css = _read("app/static/css/components.css")
    required_rules = [
        ".panel",
        ".btn",
        ".btn-primary",
        ".btn-secondary",
        ".btn-danger",
        ".input-group",
        ".input",
        ".badge",
    ]
    for rule in required_rules:
        assert rule in css


def test_system_css_exposes_white_mode_token_bridge() -> None:
    css = _read("app/static/css/system.css")
    assert "--color-bg-root" in css
    assert "--color-bg-panel" in css
    assert "--color-text-main" in css
    assert "--bg-primary: var(--color-bg-panel);" in css
    assert "body {" in css
    assert "background-color: var(--color-bg-root);" in css


def test_login_template_boot_sequence_and_error_banner_contract() -> None:
    html = _read("app/templates/login.html")
    assert 'id="bootSequence"' in html
    assert "SYSTEM READY." in html
    assert 'class="error-banner"' in html
    assert "role=\"alert\"" in html
