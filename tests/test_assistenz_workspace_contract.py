from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_assistenz_workspace_groups_and_status_cards_present() -> None:
    template = _read("app/templates/assistant.html")
    web_py = _read("app/web.py")

    assert "Assistenz" in template
    assert "Kommunikation" in web_py
    assert "Dokumente" in web_py
    assert "Baustelle / Messenger" in web_py
    assert "Zeit" in web_py
    assert "Wissen / Gedächtnis" in web_py
    assert "Fokus / Privat" in web_py
    assert "verfügbar" in web_py
    assert "vorbereitet" in web_py
    assert "geplant" in web_py
    assert 'href": "/email"' in web_py
    assert 'href": "/upload"' in web_py
    assert 'href": "/messenger"' in web_py
    assert 'href": "/time"' in web_py


def test_sidebar_contains_assistenz_in_primary_nav_and_module_disclosure() -> None:
    html = _read("app/templates/partials/sidebar.html")

    assert "'key': 'assistant'" in html
    assert "Assistenz-Module" in html
    assert "aria-label=\"Assistant öffnen\"" in html
