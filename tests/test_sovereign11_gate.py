from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_layout_enforces_white_mode() -> None:
    layout = (REPO_ROOT / "app/templates/layout.html").read_text(encoding="utf-8")
    assert "classList.add('light')" in layout
    assert "classList.remove('dark')" in layout
    assert "ks_theme', 'light'" in layout


def test_primary_shell_sets_page_ready_selector() -> None:
    layout = (REPO_ROOT / "app/templates/layout.html").read_text(encoding="utf-8")
    assert 'id="main-content" hx-history-elt data-page-ready="1"' in layout


def test_no_cdn_asset_links_in_layout() -> None:
    layout = (REPO_ROOT / "app/templates/layout.html").read_text(encoding="utf-8")
    assert "https://" not in layout
    assert "http://" not in layout
    assert "cdn." not in layout.lower()


def test_no_cdn_asset_links_in_sidebar() -> None:
    sidebar = (REPO_ROOT / "app/templates/partials/sidebar.html").read_text(encoding="utf-8")
    assert "https://" not in sidebar
    assert "http://" not in sidebar
    assert "cdn." not in sidebar.lower()
