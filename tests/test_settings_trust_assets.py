from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_foundation_css_includes_light_mode_tokens():
    css = _read("app/static/css/foundation.css")
    assert ":root" in css
    assert "--primary-600" in css
    assert "--bg-surface" in css


def test_settings_css_contains_trust_center_states():
    css = _read("app/static/css/settings.css")
    assert ".status-ok" in css
    assert ".status-warn" in css
    assert ".status-locked" in css


def test_settings_js_registers_safety_interactions():
    js = _read("app/static/js/settings.js")
    assert "confirm" in js.lower()
    assert "addEventListener" in js


def test_template_routes_still_reference_core_shell():
    settings_html = _read("app/templates/settings.html")
    messenger_html = _read("app/templates/messenger.html")
    email_html = _read("app/templates/email.html")
    assert "{% extends \"layout.html\" %}" in settings_html
    assert "{% extends \"layout.html\" %}" in messenger_html
    assert "{% extends \"layout.html\" %}" in email_html
    assert "ms-hub" in messenger_html
    assert "Email-Cockpit" in email_html
    assert "email-inbox-list" in email_html
    assert "Antwortvorschläge" in email_html
