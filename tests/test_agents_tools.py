from __future__ import annotations

from app.agents import tools


def test_tools_validation_error():
    out = tools.dispatch(
        "create_task",
        {},
        read_only_flag=False,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"]["code"] == "validation_error"


def test_tools_read_only_blocks_mutating():
    out = tools.dispatch(
        "create_task",
        {"title": "A"},
        read_only_flag=True,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"]["code"] == "read_only"


def test_export_akte_is_mutating_and_blocked():
    out = tools.dispatch(
        "export_akte",
        {"task_id": 1},
        read_only_flag=True,
        tenant_id="kukanilea",
        user="dev",
    )
    assert out["error"]["code"] == "read_only"
