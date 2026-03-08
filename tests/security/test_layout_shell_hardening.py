from __future__ import annotations

import re
from pathlib import Path


LAYOUT_PATH = Path("app/templates/layout.html")


def test_layout_shell_has_no_inline_event_handlers() -> None:
    content = LAYOUT_PATH.read_text(encoding="utf-8")
    assert re.search(r"\son[a-z]+\s*=", content, re.IGNORECASE) is None


def test_layout_shell_uses_local_assets_only() -> None:
    content = LAYOUT_PATH.read_text(encoding="utf-8")
    assert re.search(r"\b(?:src|href|poster)\s*=\s*[\"'](?:https?:)?//", content, re.IGNORECASE) is None
    assert "javascript:" not in content.lower()


def test_layout_preload_does_not_depend_on_onload_hacks() -> None:
    content = LAYOUT_PATH.read_text(encoding="utf-8")
    assert "rel=\"preload\"" in content
    assert "onload=" not in content


def test_layout_does_not_preload_inter_font_directly() -> None:
    content = LAYOUT_PATH.read_text(encoding="utf-8")
    assert "InterVariable.woff2" not in content


def test_layout_keeps_local_fonts_css_contract() -> None:
    content = LAYOUT_PATH.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="/static/css/fonts.css">' in content
