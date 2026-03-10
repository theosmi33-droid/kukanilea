from pathlib import Path


def test_chat_widget_escapes_dynamic_html_values() -> None:
    source = Path("app/web.py").read_text(encoding="utf-8")

    assert "function escHtml(v)" in source
    assert ".replace(/</g, \"&lt;\")" in source
    assert ".replace(/>/g, \"&gt;\")" in source
    assert "const label = escHtml(r.file_name || token);" in source
    assert "<div class=\"text-sm whitespace-pre-wrap\">${escHtml(text)}</div>" in source
