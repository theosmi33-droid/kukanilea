from __future__ import annotations

from app.services import api_dispatcher
from app.services.api_dispatcher import APIDispatcher


def test_process_queue_skips_online_probe_when_external_calls_disabled(monkeypatch):
    monkeypatch.delenv("KUKANILEA_EXTERNAL_CALLS_ENABLED", raising=False)

    called = {"online": False}

    def _should_not_be_called() -> bool:
        called["online"] = True
        raise AssertionError("is_online must not run when external calls are disabled")

    monkeypatch.setattr(api_dispatcher, "is_online", _should_not_be_called)

    dispatcher = APIDispatcher(auth_db_path=":memory:")
    dispatcher.process_queue()

    assert called["online"] is False
