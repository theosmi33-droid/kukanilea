from __future__ import annotations

from pathlib import Path

from flask import Flask

import kukanilea_core_v3_fixed as core
from app.autonomy.autotag import (
    autotag_rule_create,
    autotag_rule_delete,
    autotag_rule_toggle,
    autotag_rule_update,
    autotag_rules_list,
)


def _init_core(tmp_path: Path) -> None:
    core.DB_PATH = tmp_path / "core.db"
    core.BASE_PATH = tmp_path / "base"
    core.EINGANG = tmp_path / "eingang"
    core.PENDING_DIR = tmp_path / "pending"
    core.DONE_DIR = tmp_path / "done"
    core.db_init()


def _cond() -> dict:
    return {"type": "ext_in", "values": ["txt"]}


def _actions() -> list[dict]:
    return [{"type": "set_doctype", "token": "invoice"}]


def test_autotag_rule_crud_and_tenant_isolation(tmp_path: Path) -> None:
    _init_core(tmp_path)

    created = autotag_rule_create(
        "TENANT_A",
        name="Rule A",
        priority=10,
        condition_obj=_cond(),
        action_list=_actions(),
        actor_user_id="dev",
        enabled=True,
    )
    assert created["name"] == "Rule A"
    assert int(created["priority"]) == 10

    try:
        autotag_rule_create(
            "TENANT_A",
            name="Rule A",
            priority=0,
            condition_obj=_cond(),
            action_list=_actions(),
            actor_user_id="dev",
        )
    except ValueError as exc:
        assert str(exc) == "duplicate"
    else:
        raise AssertionError("expected duplicate")

    updated = autotag_rule_update(
        "TENANT_A",
        created["id"],
        name="Rule A Updated",
        priority=-5,
        actor_user_id="dev",
    )
    assert updated["name"] == "Rule A Updated"
    assert int(updated["priority"]) == -5

    toggled = autotag_rule_toggle(
        "TENANT_A", created["id"], enabled=False, actor_user_id="dev"
    )
    assert int(toggled["enabled"]) == 0

    assert len(autotag_rules_list("TENANT_A")) == 1
    assert autotag_rules_list("TENANT_B") == []

    autotag_rule_delete("TENANT_A", created["id"], actor_user_id="dev")
    assert autotag_rules_list("TENANT_A") == []


def test_autotag_rule_read_only_blocks_mutations(tmp_path: Path) -> None:
    _init_core(tmp_path)
    app = Flask(__name__)
    app.config["READ_ONLY"] = True
    with app.app_context():
        try:
            autotag_rule_create(
                "TENANT_A",
                name="Blocked",
                priority=0,
                condition_obj=_cond(),
                action_list=_actions(),
                actor_user_id="dev",
            )
        except PermissionError as exc:
            assert str(exc) == "read_only"
        else:
            raise AssertionError("expected read_only")
