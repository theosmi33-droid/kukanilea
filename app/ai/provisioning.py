from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ai.ollama_client import ollama_list_models
from app.ollama_runtime import ensure_ollama_running, pull_ollama_model

from .modelpack import import_model_pack
from .personal_memory import ensure_personal_memory_schema

_BOOTSTRAP_LOCK = threading.Lock()
_BOOTSTRAP_THREAD: threading.Thread | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _state_path(config: Mapping[str, Any]) -> Path:
    return Path(config["AI_BOOTSTRAP_STATE_FILE"])


def _modelpack_enabled(config: Mapping[str, Any]) -> bool:
    return _truthy(config.get("AI_BOOTSTRAP_USE_MODELPACK", "1"))


def _modelpack_file(config: Mapping[str, Any]) -> Path | None:
    raw = str(config.get("AI_BOOTSTRAP_MODELPACK_FILE") or "").strip()
    return Path(raw).expanduser() if raw else None


def _list_installed_models(config: Mapping[str, Any]) -> list[str]:
    base_url = str(config.get("OLLAMA_BASE_URL") or "").strip() or None
    try:
        rows = ollama_list_models(base_url=base_url, timeout_s=5)
    except Exception:
        return []
    return [str(row or "").strip() for row in rows if str(row or "").strip()]


def _has_model(installed_models: list[str], requested_model: str) -> bool:
    target = str(requested_model or "").strip().lower()
    if not target:
        return False
    target_base = target.split(":", 1)[0]
    for raw in installed_models:
        model = str(raw or "").strip().lower()
        if not model:
            continue
        if model == target:
            return True
        if model.split(":", 1)[0] == target_base:
            return True
    return False


def _attempt_modelpack_import(
    config: Mapping[str, Any],
    state: dict[str, Any],
) -> bool:
    modelpack_state = state.setdefault("modelpack", {})
    modelpack_state["enabled"] = bool(_modelpack_enabled(config))
    path = _modelpack_file(config)
    modelpack_state["path"] = str(path) if path else ""
    modelpack_state["exists"] = bool(path is not None and path.exists())

    if not modelpack_state["enabled"] or not path or not path.exists():
        modelpack_state.setdefault("attempted", False)
        modelpack_state.setdefault("imported", False)
        return False

    try:
        result = import_model_pack(pack_path=path)
    except Exception as exc:
        modelpack_state["attempted"] = True
        modelpack_state["imported"] = False
        modelpack_state["error"] = str(exc)
        return False

    modelpack_state["attempted"] = True
    modelpack_state["imported"] = bool(result.get("ok"))
    modelpack_state["result"] = result
    return bool(result.get("ok"))


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

    modelpack_path = _modelpack_file(config)
    state: dict[str, Any] = {
        "status": "running",
        "started_at": _now_iso(),
        "models": [],
        "models_ok": False,
        "ollama_ready": False,
        "installed_models_before": [],
        "installed_models_after": [],
        "modelpack": {
            "enabled": bool(_modelpack_enabled(config)),
            "path": str(modelpack_path) if modelpack_path else "",
            "exists": bool(modelpack_path and modelpack_path.exists()),
            "attempted": False,
            "imported": False,
        },
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
        installed_before = (
            _list_installed_models(config) if state["ollama_ready"] else []
        )
        state["installed_models_before"] = installed_before

        # Optional offline seed: import bundled modelpack first, then only pull missing models.
        if state["ollama_ready"]:
            _attempt_modelpack_import(config, state)

        installed = _list_installed_models(config) if state["ollama_ready"] else []
        if pull_models and state["ollama_ready"]:
            model_results: list[dict[str, Any]] = []
            for model in models:
                model_name = str(model or "").strip()
                if not model_name:
                    continue
                if _has_model(installed, model_name):
                    model_results.append(
                        {"model": model_name, "ok": True, "source": "installed"}
                    )
                    continue

                ok = bool(
                    pull_ollama_model(
                        model=model_name,
                        timeout_s=timeout,
                    )
                )
                source = "pull"
                if not ok:
                    modelpack = state.get("modelpack", {})
                    if (
                        isinstance(modelpack, dict)
                        and modelpack.get("enabled")
                        and not modelpack.get("attempted")
                    ):
                        if _attempt_modelpack_import(config, state):
                            installed = _list_installed_models(config)
                            ok = _has_model(installed, model_name)
                            source = "modelpack" if ok else source
                else:
                    installed = [*installed, model_name]

                model_results.append({"model": model_name, "ok": ok, "source": source})
            state["models"] = model_results
        else:
            state["models"] = [
                {"model": model, "ok": False, "source": "skipped"} for model in models
            ]

        state["installed_models_after"] = (
            _list_installed_models(config) if state["ollama_ready"] else []
        )
        state["models_ok"] = bool(state.get("models")) and all(
            bool(row.get("ok"))
            for row in state.get("models", [])
            if isinstance(row, dict)
        )

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
