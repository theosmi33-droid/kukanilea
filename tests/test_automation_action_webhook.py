from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import kukanilea_core_v3_fixed as core
from app.automation.actions import execute_action
from app.automation.store import create_rule
from app.config import Config


class _Response:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _set_core_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "core.sqlite3"
    monkeypatch.setattr(core, "DB_PATH", db_path)
    return db_path


def _rule_id(db_path: Path) -> str:
    return create_rule(
        tenant_id="TENANT_A",
        name="Webhook",
        triggers=[],
        conditions=[],
        actions=[],
        db_path=db_path,
    )


def test_webhook_action_succeeds_for_allowed_domain(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = _rule_id(db_path)
    monkeypatch.setattr(Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", ["hooks.example.com"])

    calls: list[Any] = []

    def _fake_urlopen(req, timeout=0):
        calls.append((req.full_url, timeout))
        return _Response(200)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "webhook",
            "url": "https://hooks.example.com/path?token=secret",
            "method": "POST",
            "body_template": '{"event":"{{event_type}}"}',
        },
        context={"event_type": "lead.created"},
        db_path=db_path,
    )
    assert result["status"] == "ok"
    assert int(result["result"]["status_code"]) == 200
    assert calls[0][0] == "https://hooks.example.com/path"


def test_webhook_action_rejects_non_allowlisted_domain(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = _rule_id(db_path)
    monkeypatch.setattr(Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", ["hooks.example.com"])

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "webhook",
            "url": "https://evil.example.com/hook",
            "method": "POST",
            "body_template": "{}",
        },
        context={},
        db_path=db_path,
    )
    assert result["status"] == "failed"
    assert result["error"] == "domain_not_allowed"


def test_webhook_action_rejects_auth_headers(tmp_path: Path, monkeypatch) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = _rule_id(db_path)
    monkeypatch.setattr(Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", ["hooks.example.com"])
    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "webhook",
            "url": "https://hooks.example.com/hook",
            "method": "POST",
            "body_template": "{}",
            "headers": {"Authorization": "Bearer secret"},
        },
        context={},
        db_path=db_path,
    )
    assert result["status"] == "failed"
    assert result["error"] == "header_not_allowed"


def test_webhook_action_retries_once_for_transient_http(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = _rule_id(db_path)
    monkeypatch.setattr(Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", ["hooks.example.com"])
    monkeypatch.setattr("time.sleep", lambda _s: None)

    calls = {"count": 0}

    def _fake_urlopen(req, timeout=0):  # noqa: ARG001
        calls["count"] += 1
        raise HTTPError(req.full_url, 500, "boom", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "webhook",
            "url": "https://hooks.example.com/hook",
            "method": "POST",
            "body_template": "{}",
        },
        context={},
        db_path=db_path,
    )
    assert result["status"] == "failed"
    assert result["error"] == "webhook_transient_http_500"
    assert calls["count"] == 2


def test_webhook_action_does_not_retry_permanent_http(
    tmp_path: Path, monkeypatch
) -> None:
    db_path = _set_core_db(tmp_path, monkeypatch)
    rule_id = _rule_id(db_path)
    monkeypatch.setattr(Config, "WEBHOOK_ALLOWED_DOMAINS_LIST", ["hooks.example.com"])

    calls = {"count": 0}

    def _fake_urlopen(req, timeout=0):  # noqa: ARG001
        calls["count"] += 1
        raise HTTPError(req.full_url, 400, "bad", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    result = execute_action(
        tenant_id="TENANT_A",
        rule_id=rule_id,
        action_config={
            "action_type": "webhook",
            "url": "https://hooks.example.com/hook",
            "method": "POST",
            "body_template": "{}",
        },
        context={},
        db_path=db_path,
    )
    assert result["status"] == "failed"
    assert result["error"] == "webhook_http_400"
    assert calls["count"] == 1
