from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_messenger_workspace_keeps_three_column_journal_contract():
    html = _read("app/templates/messenger.html")

    assert "ms-hub" in html
    assert "ms-column-left" in html
    assert "ms-column-center" in html
    assert "ms-column-right" in html
    assert "Erkannte To-dos" in html
    assert "Tagesbericht (Entwurf)" in html
    assert "Folgeaktionen" in html
