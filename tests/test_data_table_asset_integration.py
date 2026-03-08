from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_layout_loads_data_table_assets_once() -> None:
    html = _read("app/templates/layout.html")
    assert html.count('/static/css/data-table.css') == 1
    assert html.count('/static/js/data-table.js') == 1
    assert '<script src="/static/js/data-table.js" defer></script>' in html


def test_data_table_js_enhances_tables_with_controls() -> None:
    js = _read("app/static/js/data-table.js")
    assert "table.dataset.enhanced = '1'" in js
    assert "data-table-shell" in js
    assert "data-table-toolbar" in js
    assert "data-table-search" in js
    assert "data-filter-chip" in js


def test_data_table_js_supports_sort_filter_and_selection() -> None:
    js = _read("app/static/js/data-table.js")
    assert "sortTable(table" in js
    assert "setupColumnResize" in js
    assert "select all rows" in js.lower()
    assert "is-selected" in js
    assert "search.addEventListener('input'" in js


def test_data_table_css_contains_shell_and_interaction_states() -> None:
    css = _read("app/static/css/data-table.css")
    expected_selectors = [
        ".data-table-shell",
        ".data-table-cards",
        ".data-table-toolbar",
        ".data-filter-chip.active",
        "table.js-data-table tr.is-selected td",
        ".sortable-header.sort-asc::after",
        ".sortable-header.sort-desc::after",
        ".resize-handle",
    ]
    for selector in expected_selectors:
        assert selector in css
