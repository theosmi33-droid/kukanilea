from __future__ import annotations

from pathlib import Path


def test_messenger_template_escapes_dynamic_innerhtml_fields() -> None:
    html = Path("app/templates/messenger.html").read_text(encoding="utf-8")

    assert "const safeTitle = escapeHtml(thread.title);" in html
    assert "const safeProvider = escapeHtml(thread.provider);" in html
    assert "const safeMode = escapeHtml(spec.mode);" in html
    assert "const safeStatus = escapeHtml(spec.status);" in html
    assert "const safeSummary = escapeHtml(a.summary);" in html
    assert "${thread.title}" not in html
    assert "${spec.status}" not in html
    assert "${a.summary}" not in html


def test_messenger_escape_html_covers_quotes() -> None:
    html = Path("app/templates/messenger.html").read_text(encoding="utf-8")

    assert ".replaceAll('\"', '&quot;')" in html
    assert "replaceAll(\"'\", '&#39;')" in html
