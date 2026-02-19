from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_design_system_docs_exist() -> None:
    assert (ROOT / "docs" / "DESIGN_SYSTEM.md").exists()
    assert (ROOT / "docs" / "FOUNDATION_PROCESS_NOTE.md").exists()


def test_component_macro_files_exist() -> None:
    components = ROOT / "templates" / "components"
    assert (components / "button.html").exists()
    assert (components / "alert.html").exists()
    assert (components / "form.html").exists()
    assert (components / "page_header.html").exists()


def test_app_shell_supports_mobile_nav() -> None:
    web_py = (ROOT / "app" / "web.py").read_text(encoding="utf-8")
    assert 'id="appNav"' in web_py
    assert 'id="appNavOverlay"' in web_py
    assert 'id="navToggle"' in web_py
    assert "toggleNav" in web_py


def test_refactored_templates_use_component_macros() -> None:
    files = [
        ROOT / "templates" / "automation" / "index.html",
        ROOT / "templates" / "knowledge" / "search.html",
        ROOT / "templates" / "omni" / "inbox.html",
        ROOT / "templates" / "crm" / "customers.html",
        ROOT / "templates" / "crm" / "deals.html",
        ROOT / "templates" / "crm" / "quotes.html",
        ROOT / "templates" / "crm" / "customer_detail.html",
        ROOT / "templates" / "crm" / "quote_detail.html",
        ROOT / "templates" / "crm" / "emails_import.html",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "components/button.html" in text


def test_refactored_tables_no_inline_border_style() -> None:
    files = [
        ROOT / "templates" / "omni" / "inbox.html",
        ROOT / "templates" / "crm" / "quote_detail.html",
        ROOT / "templates" / "crm" / "emails_import.html",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert 'style="border-color:var(--border)"' not in text
