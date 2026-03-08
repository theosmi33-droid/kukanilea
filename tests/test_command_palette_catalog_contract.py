from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_command_palette_is_loaded_from_layout_shell() -> None:
    layout = _read("app/templates/layout.html")
    assert '<script src="/static/js/command_palette.js" defer></script>' in layout


def test_command_palette_defines_expected_command_groups() -> None:
    js = _read("static/js/command_palette.js")
    assert "category: 'navigation'" in js
    assert "category: 'actions'" in js
    assert "category: 'entities'" in js
    assert "category: 'files'" in js
    assert "category: 'agents'" in js


def test_command_palette_uses_existing_system_logs_route() -> None:
    js = _read("static/js/command_palette.js")
    assert "path: '/system/logs'" in js
    assert "path: '/system_logs'" not in js


def test_command_palette_keyboard_and_filtering_contract_present() -> None:
    js = _read("static/js/command_palette.js")
    assert "event.key.toLowerCase() === 'k'" in js
    assert "event.key === 'Escape'" in js
    assert "event.key === 'ArrowDown'" in js
    assert "event.key === 'ArrowUp'" in js
    assert "event.key === 'Enter'" in js
    assert "this.filteredCommands" in js
    assert "this.resultsContainer.innerHTML" in js


def test_command_palette_stays_local_and_does_not_embed_external_targets() -> None:
    js = _read("static/js/command_palette.js")
    assert "http://" not in js
    assert "https://" not in js
    assert "javascript:" not in js.lower()
