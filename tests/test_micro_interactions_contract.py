from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_motion_css_contains_reveal_and_toast_animations() -> None:
    css = _read("app/static/css/motion.css")
    assert "--reveal-duration" in css
    assert "@keyframes pageReveal" in css
    assert ".reveal-item" in css
    assert ".toast {" in css
    assert "@keyframes toastIn" in css
    assert "@keyframes toastOut" in css
    assert ".confirm-backdrop" in css
    assert ".confirm-dialog" in css


def test_motion_css_keeps_confirm_risk_visual_states() -> None:
    css = _read("app/static/css/motion.css")
    assert ".floating-chat-confirm-risk[data-risk-level=\"medium\"]" in css
    assert ".floating-chat-confirm-risk[data-risk-level=\"high\"]" in css
    assert ".floating-chat-confirm-preview" in css
    assert "#floating-chat-confirm-actions" in css


def test_motion_css_respects_reduced_motion_policy() -> None:
    css = _read("app/static/css/motion.css")
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "animation-duration: 0.01ms !important;" in css
    assert "transition-duration: 0.01ms !important;" in css
    assert "scroll-behavior: auto !important;" in css


def test_sovereign_shell_css_contains_loading_and_disclosure_contracts() -> None:
    css = _read("app/static/css/sovereign-shell.css")
    required = [
        "body[data-htmx-loading=\"1\"] #main-content",
        ".htmx-indicator-soft",
        "@keyframes sovereignLoading",
        "#main-content.loading-skeleton .card",
        "#main-content.loading-skeleton .panel",
        "[data-disclosure-panel]",
        "[data-disclosure-panel].is-open",
        "html.sidebar-collapsed .nav-text",
    ]
    for token in required:
        assert token in css


def test_navigation_js_initializes_motion_loading_and_disclosure() -> None:
    js = _read("app/static/js/navigation.js")
    assert "window.__kukanileaNavigationMotionInit" in js
    assert "setupPressedState();" in js
    assert "setupHtmxLoadingFeedback();" in js
    assert "setupDisclosure();" in js
    assert "setupAutoAriaLabels();" in js
    assert "markCurrentNavigation();" in js


def test_navigation_js_tracks_htmx_loading_state_and_accessibility() -> None:
    js = _read("app/static/js/navigation.js")
    assert "document.body.setAttribute('data-htmx-loading'" in js
    assert "contentRoot.classList.toggle('loading-skeleton'" in js
    assert "contentRoot.setAttribute('aria-busy'" in js
    assert "document.body.addEventListener('htmx:beforeRequest'" in js
    assert "document.body.addEventListener('htmx:afterRequest'" in js
    assert "document.body.addEventListener('htmx:responseError'" in js
    assert "document.body.addEventListener('htmx:sendError'" in js
    assert "markCurrentNavigation();" in js
