from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.actions import execute_action
from app.automation.store import create_rule


def _set_core_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core, "DB_PATH", db_path)
    return db_path


def _seed_contacts(db_path: Path, *, tenant_id: str, emails: list[str]) -> None:
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts(
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              email TEXT
            )
            """
        )
        for idx, email in enumerate(emails, start=1):
            con.execute(
                "INSERT INTO contacts(id, tenant_id, email) VALUES (?,?,?)",
                (f"c-{idx}", tenant_id, email),
            )
        con.commit()
    finally:
        con.close()


def test_email_draft_action_creates_postfach_draft(tmp_path: Path, monkeypatch) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    _seed_contacts(db_path, tenant_id="TENANT_A", emails=["kunde@example.com"])
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Email draft",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    captured: dict[str, str] = {}

    def _fake_create_draft(
        _db_path: Path,
        *,
        tenant_id: str,
        account_id: str,
        thread_id: str | None,
        to_value: str,
        subject_value: str,
        body_value: str,
    ) -> str:
        captured["tenant_id"] = tenant_id
        captured["account_id"] = account_id
        captured["thread_id"] = str(thread_id or "")
        captured["to_value"] = to_value
        captured["subject_value"] = subject_value
        captured["body_value"] = body_value
        return "draft-1"

    monkeypatch.setattr(
        "app.automation.actions.postfach_create_draft", _fake_create_draft
    )
    monkeypatch.setattr(
        "app.automation.actions.postfach_list_accounts",
        lambda _db, _tenant: [{"id": "acc-1"}],
    )

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "email_draft",
            "to": ["kunde@example.com"],
            "subject": "Status",
            "body_template": "Hallo {customer_name}",
        },
        context={"customer_name": "Demo GmbH"},
        db_path=db_path,
        user_confirmed=True,
    )
    assert result["status"] == "ok"
    assert result["result"]["draft_id"] == "draft-1"
    assert captured["account_id"] == "acc-1"
    assert captured["to_value"] == "kunde@example.com"
    assert "Demo GmbH" in captured["body_value"]


def test_email_draft_action_fails_for_non_crm_recipient(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    _seed_contacts(db_path, tenant_id="TENANT_A", emails=["other@example.com"])
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Email draft",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(
        "app.automation.actions.postfach_list_accounts",
        lambda _db, _tenant: [{"id": "acc-1"}],
    )
    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "email_draft",
            "to": "kunde@example.com",
            "subject": "Status",
            "body_template": "Hallo",
        },
        context={},
        db_path=db_path,
        user_confirmed=True,
    )
    assert result["status"] == "failed"
    assert result["error"] == "recipient_not_in_crm"


def test_email_draft_action_fails_when_account_missing(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    _seed_contacts(db_path, tenant_id="TENANT_A", emails=["kunde@example.com"])
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Email draft",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )
    monkeypatch.setattr(
        "app.automation.actions.postfach_list_accounts",
        lambda _db, _tenant: [],
    )
    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "email_draft",
            "to": "kunde@example.com",
            "subject": "Status",
            "body_template": "Hallo",
        },
        context={},
        db_path=db_path,
        user_confirmed=True,
    )
    assert result["status"] == "failed"
    assert result["error"] == "account_not_configured"
