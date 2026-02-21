from __future__ import annotations

from pathlib import Path

import app.automation as automation
import app.update as update_mod
import app.web as web
from app.ai import provider_router
from app.startup_maintenance import (
    load_startup_maintenance_state,
    run_startup_maintenance,
    start_startup_maintenance_background,
)


def test_run_startup_maintenance_writes_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        web.core, "index_warmup", lambda tenant_id="": {"ok": True, "tenant": tenant_id}
    )
    monkeypatch.setattr(
        automation,
        "get_or_build_daily_insights",
        lambda tenant_id, day=None: {"cached": True, "tenant": tenant_id, "day": day},
    )
    monkeypatch.setattr(
        provider_router,
        "provider_health_snapshot",
        lambda **kwargs: {"ok": True, "providers": [], "kwargs": kwargs},
    )
    monkeypatch.setattr(
        update_mod,
        "check_for_installable_update",
        lambda *args, **kwargs: {"checked": True, "update_available": False},
    )

    state_path = tmp_path / "startup_state.json"
    cfg = {
        "TENANT_DEFAULT": "KUKANILEA",
        "STARTUP_MAINTENANCE_STATE_FILE": state_path,
        "UPDATE_CHECK_ENABLED": True,
        "UPDATE_CHECK_URL": "https://example.invalid/releases/latest",
        "UPDATE_CHECK_TIMEOUT_SECONDS": 1,
        "UPDATE_MANIFEST_URL": "",
        "UPDATE_SIGNING_REQUIRED": False,
        "UPDATE_SIGNING_PUBLIC_KEY": "",
    }
    result = run_startup_maintenance(cfg)
    assert result["status"] == "done"
    assert result["ok"] is True
    assert state_path.exists()
    loaded = load_startup_maintenance_state(cfg)
    assert loaded.get("status") == "done"
    assert isinstance(loaded.get("steps"), list)
    assert {str(s.get("name")) for s in loaded["steps"]} == {
        "index_warmup",
        "insights_cache",
        "provider_health_prefetch",
        "update_check",
    }


def test_start_startup_maintenance_background_respects_disabled_flag(
    tmp_path: Path,
) -> None:
    cfg = {
        "STARTUP_MAINTENANCE_ENABLED": False,
        "STARTUP_MAINTENANCE_STATE_FILE": tmp_path / "state.json",
    }
    assert start_startup_maintenance_background(cfg) is None
