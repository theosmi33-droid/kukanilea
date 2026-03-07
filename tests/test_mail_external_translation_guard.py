from __future__ import annotations

import json
from pathlib import Path

from app.config import Config
from app.plugins.mail import MailAgent, MailInput, MailOptions


def _write_settings(root: Path, *, external_apis_enabled: bool, external_translation_enabled: bool) -> None:
    payload = {
        "external_apis_enabled": external_apis_enabled,
        "external_translation_enabled": external_translation_enabled,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "system_settings.json").write_text(json.dumps(payload), encoding="utf-8")


def _mail_input() -> MailInput:
    return MailInput(context="Test", facts={}, attachments=[])


def test_external_translation_blocked_when_feature_flag_off(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    _write_settings(tmp_path, external_apis_enabled=False, external_translation_enabled=False)

    called = {"post": 0}

    def _blocked_post(*args, **kwargs):
        called["post"] += 1
        raise AssertionError("external request must not be called when feature flag is off")

    monkeypatch.setattr("app.plugins.mail.requests.post", _blocked_post)

    agent = MailAgent()
    monkeypatch.setattr(agent, "deepl_api_key", "dummy")
    result = agent.generate(_mail_input(), MailOptions(rewrite_mode="deepl_api", external_translation_opt_in=True))

    assert called["post"] == 0
    assert any(
        event["action"] == "mail.translation.external"
        and event["status"] == "blocked"
        and event["meta"].get("reason") == "feature_flag_disabled"
        for event in result["audit_events"]
    )


def test_external_translation_allowed_when_flag_on(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    _write_settings(tmp_path, external_apis_enabled=True, external_translation_enabled=True)

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"translations": [{"text": "Übersetzter Text"}]}

    called = {"post": 0}

    def _fake_post(*args, **kwargs):
        called["post"] += 1
        return _Response()

    monkeypatch.setattr("app.plugins.mail.requests.post", _fake_post)

    agent = MailAgent()
    monkeypatch.setattr(agent, "deepl_api_key", "dummy")
    result = agent.generate(_mail_input(), MailOptions(rewrite_mode="deepl_api", external_translation_opt_in=True))

    assert called["post"] == 1
    assert result["body"] == "Übersetzter Text"
    assert any(
        event["action"] == "mail.translation.external" and event["status"] == "allowed"
        for event in result["audit_events"]
    )


def test_external_translation_requires_explicit_opt_in(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Config, "USER_DATA_ROOT", tmp_path)
    _write_settings(tmp_path, external_apis_enabled=True, external_translation_enabled=True)

    called = {"post": 0}

    def _blocked_post(*args, **kwargs):
        called["post"] += 1
        raise AssertionError("external request must not be called without explicit opt-in")

    monkeypatch.setattr("app.plugins.mail.requests.post", _blocked_post)

    agent = MailAgent()
    monkeypatch.setattr(agent, "deepl_api_key", "dummy")
    result = agent.generate(_mail_input(), MailOptions(rewrite_mode="deepl_api"))

    assert called["post"] == 0
    assert any(
        event["action"] == "mail.translation.external"
        and event["status"] == "blocked"
        and event["meta"].get("reason") == "opt_in_required"
        for event in result["audit_events"]
    )
