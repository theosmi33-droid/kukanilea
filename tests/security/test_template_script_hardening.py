from pathlib import Path


def test_layout_shell_logic_loaded_from_external_asset() -> None:
    layout = Path("app/templates/layout.html").read_text(encoding="utf-8")

    assert '/static/js/layout-shell.js' in layout
    assert 'let chatPendingId = \'' not in layout
    assert 'async function sendChatMessage()' not in layout


def test_layout_shell_asset_contains_chat_controller_logic() -> None:
    script = Path("app/static/js/layout-shell.js").read_text(encoding="utf-8")

    assert 'let chatPendingId = \'' in script
    assert 'async function sendChatMessage()' in script
    assert "fetch('/api/chat/compact'" in script
    assert '.innerHTML' not in script
