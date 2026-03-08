from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_layout_has_no_inline_onload_in_shell_css_links() -> None:
    html = _read("app/templates/layout.html")
    assert 'onload="this.media=' not in html
    assert "InterVariable.woff2" not in html
    assert '<link rel="preload" href="/static/css/toast.css" as="style">' in html
    assert '<link rel="preload" href="/static/css/motion.css" as="style">' in html
    assert '<link rel="stylesheet" href="/static/css/toast.css">' in html
    assert '<link rel="stylesheet" href="/static/css/motion.css">' in html


def test_tasks_performance_script_exists_and_initializes_once() -> None:
    js = _read("app/static/js/tasks-performance.js")
    assert "window.__tasksPerfInitialized" in js
    assert "const root = document.getElementById('tasks-virtualized');" in js
    assert "if (!root) return;" in js


def test_tasks_performance_virtualization_contract_present() -> None:
    js = _read("app/static/js/tasks-performance.js")
    assert "const viewportHeight = viewport.clientHeight || 480;" in js
    assert "const visibleCount = Math.ceil(viewportHeight / state.rowHeight) + state.overscan;" in js
    assert "const topSpacer = start * state.rowHeight;" in js
    assert "const bottomSpacer = Math.max(0, (total - end) * state.rowHeight);" in js
    assert "body.replaceChildren(fragment);" in js


def test_tasks_performance_search_and_cache_contract_present() -> None:
    js = _read("app/static/js/tasks-performance.js")
    assert "const textCache = new Map();" in js
    assert "const filterCache = new Map();" in js
    assert "memoizedTaskText(i).includes(key)" in js
    assert "const applySearch = debounce(() => {" in js
    assert "searchInput.addEventListener('input', applySearch" in js


def test_tasks_performance_escapes_html_in_rendered_rows() -> None:
    js = _read("app/static/js/tasks-performance.js")
    assert "const escapeHtml = (value)" in js
    assert "&lt;" in js
    assert "&gt;" in js
    assert "&quot;" in js
    assert "&#39;" in js
