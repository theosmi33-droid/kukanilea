from __future__ import annotations

from pathlib import Path


WEB_PATH = Path(__file__).resolve().parents[2] / "app" / "web.py"


def _web_text() -> str:
    return WEB_PATH.read_text(encoding="utf-8")


def test_time_widget_escapes_untrusted_entry_fields_before_innerhtml() -> None:
    text = _web_text()

    assert "function escapeHtml(value)" in text
    assert "${escapeHtml(entry.project_name || \"Ohne Projekt\")}" in text
    assert "${escapeHtml(entry.note)}" in text
    assert "${entry.note}" not in text


def test_chat_widget_escapes_text_and_token_interpolation() -> None:
    text = _web_text()

    assert "function escHtml(value)" in text
    assert "function escJsSingle(value)" in text
    assert "const safeToken = escHtml(escJsSingle(token));" in text
    assert "${escHtml(text)}" in text
    assert "openToken('${a.token}')" not in text
    assert "openToken('${token}')" not in text


def test_chat_widget_suggestions_escape_label_and_data_payload() -> None:
    text = _web_text()

    assert "data-q=\"${escHtml(s)}\"" in text
    assert ">${escHtml(s)}</button>`" in text
