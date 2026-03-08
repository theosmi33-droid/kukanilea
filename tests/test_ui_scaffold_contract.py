from __future__ import annotations

from pathlib import Path


UI_ROOT = Path("ui")


def test_ui_scaffold_files_exist() -> None:
    expected = {
        "README.md",
        "index.css",
        "design-system/tokens.css",
        "design-system/foundations.css",
        "components/buttons.css",
        "components/cards.css",
        "components/forms.css",
        "components/feedback.css",
        "layouts/app-shell.css",
        "layouts/page.css",
    }
    actual = {
        p.relative_to(UI_ROOT).as_posix()
        for p in UI_ROOT.rglob("*")
        if p.is_file()
    }
    assert expected.issubset(actual)


def test_ui_index_css_imports_all_layers() -> None:
    text = (UI_ROOT / "index.css").read_text(encoding="utf-8")
    assert '@import url("./design-system/foundations.css");' in text
    assert '@import url("./components/buttons.css");' in text
    assert '@import url("./components/cards.css");' in text
    assert '@import url("./components/forms.css");' in text
    assert '@import url("./components/feedback.css");' in text
    assert '@import url("./layouts/app-shell.css");' in text
    assert '@import url("./layouts/page.css");' in text


def test_ui_tokens_define_white_mode_core_variables() -> None:
    tokens_css = (UI_ROOT / "design-system/tokens.css").read_text(encoding="utf-8")
    assert ":root" in tokens_css
    assert "--surface-page:" in tokens_css
    assert "--surface-panel:" in tokens_css
    assert "--text-heading:" in tokens_css
    assert "--space-4:" in tokens_css
    assert "--radius-md:" in tokens_css


def test_ui_foundations_consume_design_tokens() -> None:
    foundations_css = (UI_ROOT / "design-system/foundations.css").read_text(encoding="utf-8")
    assert "var(--surface-page)" in foundations_css
    assert "var(--text-body)" in foundations_css
    assert "var(--space-" in foundations_css


def test_ui_buttons_define_primary_and_focus_states() -> None:
    buttons_css = (UI_ROOT / "components/buttons.css").read_text(encoding="utf-8")
    assert ".btn" in buttons_css
    assert ".btn-primary" in buttons_css
    foundations_css = (UI_ROOT / "design-system/foundations.css").read_text(encoding="utf-8")
    assert ":focus-visible" in foundations_css


def test_ui_readme_contains_migration_plan_and_scope() -> None:
    readme = (UI_ROOT / "README.md").read_text(encoding="utf-8")
    lowered = readme.lower()
    assert "migration" in lowered
    assert "white mode" in lowered or "white-mode" in lowered
    assert "tokens" in lowered
