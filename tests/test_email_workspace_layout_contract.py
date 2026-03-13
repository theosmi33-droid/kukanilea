from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_email_workspace_keeps_three_column_work_area_contract():
    html = _read("app/templates/email.html")

    assert "email-workspace-grid" in html
    assert "email-column-inbox" in html
    assert "email-column-thread" in html
    assert "email-column-assistant" in html
    assert "Kontakt-Tags" in html
    assert "Antwortvorschläge" in html
