from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.ollama_runtime import ensure_ollama_running, pull_ollama_model

from .personal_memory import ensure_personal_memory_schema

_BOOTSTRAP_LOCK = threading.Lock()
_BOOTSTRAP_THREAD: threading.Thread | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _state_path(config: Mapping[str, Any]) -> Path:
    return Path(config["AI_BOOTSTRAP_STATE_FILE"])


def _parse_csv_models(raw: object) -> list[str]:
    out: list[str] = []
    for part in str(raw or "").split(","):
        model = str(part or "").strip()
        if model and model not in out:
            out.append(model)
    return out


def configured_ollama_models(config: Mapping[str, Any]) -> list[str]:
    override = _parse_csv_models(config.get("AI_BOOTSTRAP_MODEL_LIST", ""))
    if override:
        return override
    default_model = str(config.get("OLLAMA_MODEL") or "").strip()
    fallback = _parse_csv_models(config.get("OLLAMA_MODEL_FALLBACKS", ""))
    out: list[str] = []
    for row in [default_model, *fallback]:
        if row and row not in out:
            out.append(row)
    return out


def load_bootstrap_state(config: Mapping[str, Any]) -> dict[str, Any]:
    path = _state_path(config)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_bootstrap_state(config: Mapping[str, Any], state: dict[str, Any]) -> None:
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_first_install_bootstrap(
    config: Mapping[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    enabled = _truthy(config.get("AI_BOOTSTRAP_ON_FIRST_RUN", "1"))
    existing = load_bootstrap_state(config)
    if not enabled:
        return existing or {"status": "disabled"}
    if existing.get("status") == "done" and not force:
        return existing

    state: dict[str, Any] = {
        "status": "running",
        "started_at": _now_iso(),
        "models": [],
        "ollama_ready": False,
        "personal_memory_schema_ready": False,
        "ok": False,
    }
    _write_bootstrap_state(config, state)

    pull_models = _truthy(config.get("AI_BOOTSTRAP_PULL_MODELS", "1"))
    timeout = int(config.get("AI_BOOTSTRAP_MODEL_PULL_TIMEOUT_SECONDS", 1800) or 1800)
    models = configured_ollama_models(config)

    try:
        state["ollama_ready"] = bool(
            ensure_ollama_running(
                wait_for_ready=True,
                timeout_s=int(config.get("OLLAMA_AUTOSTART_TIMEOUT_SECONDS", 20) or 20),
            )
        )
        if pull_models and state["ollama_ready"]:
            model_results: list[dict[str, Any]] = []
            for model in models:
                ok = bool(
                    pull_ollama_model(
                        model=model,
                        timeout_s=timeout,
                    )
                )
                model_results.append({"model": model, "ok": ok})
            state["models"] = model_results
        else:
            state["models"] = [{"model": model, "ok": False} for model in models]

        ensure_personal_memory_schema()
        state["personal_memory_schema_ready"] = True
        state["status"] = "done"
        state["ok"] = bool(
            state["ollama_ready"] and state["personal_memory_schema_ready"]
        )
        state["finished_at"] = _now_iso()
        _write_bootstrap_state(config, state)
        return state
    except Exception as exc:
        state["status"] = "error"
        state["ok"] = False
        state["error"] = str(exc)
        state["finished_at"] = _now_iso()
        _write_bootstrap_state(config, state)
        return state


def start_first_install_bootstrap_background(
    config: Mapping[str, Any],
) -> threading.Thread | None:
    if not _truthy(config.get("AI_BOOTSTRAP_ON_FIRST_RUN", "1")):
        return None
    existing = load_bootstrap_state(config)
    if existing.get("status") == "done":
        return None

    global _BOOTSTRAP_THREAD
    with _BOOTSTRAP_LOCK:
        if _BOOTSTRAP_THREAD is not None and _BOOTSTRAP_THREAD.is_alive():
            return _BOOTSTRAP_THREAD

        thread = threading.Thread(
            target=run_first_install_bootstrap,
            kwargs={"config": config, "force": False},
            name="kukanilea-ai-bootstrap",
            daemon=True,
        )
        thread.start()
        _BOOTSTRAP_THREAD = thread
        return thread
