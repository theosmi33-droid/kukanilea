from __future__ import annotations

from app.modules.messenger import parse_chat_intake


def test_parse_chat_intake_marks_create_task_as_confirm_required() -> None:
    payload = parse_chat_intake(
        "Bitte Aufgabe fuer Kunde erstellen",
        actions=[{"type": "create_task"}],
    )

    suggested = payload["suggested_next_actions"]
    assert suggested
    assert suggested[0]["type"] == "create_task"
    assert suggested[0]["confirm_required"] is True


def test_parse_chat_intake_ignores_malformed_actions_without_crash() -> None:
    payload = parse_chat_intake(
        "Nur zur Info",
        actions=["bad", None, {"type": "read_status"}],
    )

    assert payload["suggested_next_actions"] == [
        {"type": "read_status", "confirm_required": False, "reason": "read_or_assistive"}
    ]
