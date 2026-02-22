from __future__ import annotations

import json
import threading
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.version import __version__

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _state_path(config: Mapping[str, Any]) -> Path:
    configured = str(config.get("STARTUP_MAINTENANCE_STATE_FILE") or "").strip()
    if configured:
        return Path(configured)
    root = Path(config.get("USER_DATA_ROOT") or Path.home())
    return root / "startup_maintenance_state.json"


def _write_state(config: Mapping[str, Any], payload: dict[str, Any]) -> None:
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_startup_maintenance_state(config: Mapping[str, Any]) -> dict[str, Any]:
    path = _state_path(config)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _run_step(name: str, fn) -> dict[str, Any]:  # noqa: ANN001
    started = time.monotonic()
    try:
        result = fn()
        return {
            "name": str(name),
            "ok": True,
            "secs": round(time.monotonic() - started, 3),
            "result": result
            if isinstance(result, (dict, list, str, int, float, bool))
            else str(result),
            "error": "",
        }
    except Exception as exc:
        return {
            "name": str(name),
            "ok": False,
            "secs": round(time.monotonic() - started, 3),
            "result": {},
            "error": str(exc),
        }


def run_startup_maintenance(config: Mapping[str, Any]) -> dict[str, Any]:
    tenant_id = str(config.get("TENANT_DEFAULT") or "KUKANILEA")
    started_at = _now_iso()
    steps: list[dict[str, Any]] = []

    def _index_warmup():
        from app import web

        if not callable(getattr(web.core, "index_warmup", None)):
            return {"skipped": "index_warmup_missing"}
        return web.core.index_warmup(tenant_id=tenant_id)

    def _insights_cache():
        from app.automation import get_or_build_daily_insights

        return get_or_build_daily_insights(tenant_id=tenant_id)

    def _provider_health():
        from app.ai.provider_router import provider_health_snapshot

        return provider_health_snapshot(tenant_id=tenant_id, role="DEV")

    def _update_check():
        from app.update import check_for_installable_update

        enabled = bool(config.get("UPDATE_CHECK_ENABLED", False))
        if not enabled:
            return {"skipped": "update_check_disabled"}
        return check_for_installable_update(
            __version__,
            release_url=str(config.get("UPDATE_CHECK_URL") or ""),
            timeout_seconds=int(config.get("UPDATE_CHECK_TIMEOUT_SECONDS") or 5),
            manifest_url=str(config.get("UPDATE_MANIFEST_URL") or ""),
            signing_required=bool(config.get("UPDATE_SIGNING_REQUIRED", False)),
            public_key_pem=str(config.get("UPDATE_SIGNING_PUBLIC_KEY") or ""),
        )

    steps.append(_run_step("index_warmup", _index_warmup))
    steps.append(_run_step("insights_cache", _insights_cache))
    steps.append(_run_step("provider_health_prefetch", _provider_health))
    steps.append(_run_step("update_check", _update_check))

    payload = {
        "status": "done",
        "started_at": started_at,
        "finished_at": _now_iso(),
        "tenant_id": tenant_id,
        "ok": all(bool(step.get("ok")) for step in steps),
        "steps": steps,
    }
    _write_state(config, payload)
    return payload


def start_startup_maintenance_background(
    config: Mapping[str, Any],
) -> threading.Thread | None:
    enabled = bool(config.get("STARTUP_MAINTENANCE_ENABLED", True))
    if not enabled:
        return None

    global _THREAD
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return _THREAD
        thread = threading.Thread(
            target=run_startup_maintenance,
            kwargs={"config": config},
            name="kukanilea-startup-maintenance",
            daemon=True,
        )
        thread.start()
        _THREAD = thread
        return thread
