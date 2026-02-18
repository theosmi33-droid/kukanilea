from __future__ import annotations

import sqlite3
from pathlib import Path

import kukanilea_core_v3_fixed as core
from app.automation.actions import execute_action
from app.automation.store import create_rule, list_pending_actions


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


def _mock_oauth(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.automation.actions.postfach_list_accounts",
        lambda _db, _tenant: [
            {
                "id": "acc-1",
                "auth_mode": "oauth_google",
                "oauth_provider": "google",
            }
        ],
    )
    monkeypatch.setattr(
        "app.automation.actions.postfach_get_oauth_token",
        lambda *_args, **_kwargs: {
            "access_token": "token-1",
            "expires_at": "2999-01-01T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        "app.automation.actions.postfach_oauth_token_expired",
        lambda _expires_at: False,
    )


def test_email_send_action_creates_pending_until_confirmed(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    _seed_contacts(db_path, tenant_id="TENANT_A", emails=["kunde@example.com"])
    _mock_oauth(monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Email send",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "email_send",
            "to": ["kunde@example.com"],
            "subject": "Status",
            "body_template": "Hallo {customer_name}",
        },
        context={"customer_name": "Demo GmbH", "event_type": "email.received"},
        db_path=db_path,
        user_confirmed=False,
    )
    assert result["status"] == "pending"
    pending = list_pending_actions(tenant_id="TENANT_A", db_path=db_path)
    assert len(pending) == 1
    assert str(pending[0]["action_type"] or "") == "email_send"


def test_email_send_action_executes_on_confirmed_run(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    _seed_contacts(db_path, tenant_id="TENANT_A", emails=["kunde@example.com"])
    _mock_oauth(monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Email send",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )

    monkeypatch.setattr(
        "app.automation.actions.postfach_create_draft",
        lambda *_args, **_kwargs: "draft-1",
    )
    monkeypatch.setattr(
        "app.automation.actions.postfach_send_draft",
        lambda *_args, **_kwargs: {
            "ok": True,
            "thread_id": "thread-1",
            "message_id": "msg-1",
        },
    )

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "email_send",
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


def test_email_send_action_fails_for_invalid_recipient(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    _seed_contacts(db_path, tenant_id="TENANT_A", emails=["other@example.com"])
    _mock_oauth(monkeypatch)
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Email send",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "email_send",
            "to": ["kunde@example.com"],
            "subject": "Status",
            "body_template": "Hallo",
        },
        context={},
        db_path=db_path,
        user_confirmed=False,
    )
    assert result["status"] == "failed"
    assert result["error"] == "recipient_not_in_crm"
    assert list_pending_actions(tenant_id="TENANT_A", db_path=db_path) == []


def test_email_send_action_fails_without_oauth_account(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    _seed_contacts(db_path, tenant_id="TENANT_A", emails=["kunde@example.com"])
    rule_id = create_rule(
        tenant_id="TENANT_A",
        name="Email send",
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
            "action_type": "email_send",
            "to": ["kunde@example.com"],
            "subject": "Status",
            "body_template": "Hallo",
        },
        context={},
        db_path=db_path,
        user_confirmed=False,
    )
    assert result["status"] == "failed"
    assert result["error"] == "oauth_account_unavailable"
