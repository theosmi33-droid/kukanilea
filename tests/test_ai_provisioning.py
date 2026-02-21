from __future__ import annotations

import json
from pathlib import Path

from app.ai import provisioning


def _config(tmp_path: Path) -> dict[str, object]:
    return {
        "AI_BOOTSTRAP_ON_FIRST_RUN": True,
        "AI_BOOTSTRAP_PULL_MODELS": True,
        "AI_BOOTSTRAP_MODEL_LIST": "",
        "AI_BOOTSTRAP_MODEL_PULL_TIMEOUT_SECONDS": 60,
        "AI_BOOTSTRAP_USE_MODELPACK": False,
        "AI_BOOTSTRAP_MODELPACK_FILE": "",
        "AI_BOOTSTRAP_STATE_FILE": tmp_path / "ai_bootstrap_state.json",
        "OLLAMA_MODEL": "llama3.2:3b",
        "OLLAMA_MODEL_FALLBACKS": "llama3.1:8b,qwen2.5:3b",
        "OLLAMA_AUTOSTART_TIMEOUT_SECONDS": 1,
        "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
        "AI_MEMORY_DB": tmp_path / "ai_memory.sqlite3",
    }


def test_configured_ollama_models_uses_default_and_fallbacks(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    assert provisioning.configured_ollama_models(cfg) == [
        "llama3.2:3b",
        "llama3.1:8b",
        "qwen2.5:3b",
    ]


def test_run_first_install_bootstrap_writes_state(tmp_path: Path, monkeypatch) -> None:
    cfg = _config(tmp_path)

    monkeypatch.setattr(provisioning, "ensure_ollama_running", lambda **kwargs: True)
    monkeypatch.setattr(provisioning, "_list_installed_models", lambda config: [])
    pulls: list[str] = []

    def _pull(*, model: str, timeout_s: int = 0) -> bool:
        pulls.append(model)
        return True

    monkeypatch.setattr(provisioning, "pull_ollama_model", _pull)

    state = provisioning.run_first_install_bootstrap(cfg, force=True)
    assert state["status"] == "done"
    assert state["ok"] is True
    assert pulls == ["llama3.2:3b", "llama3.1:8b", "qwen2.5:3b"]

    state_path = Path(cfg["AI_BOOTSTRAP_STATE_FILE"])
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["status"] == "done"


def test_run_first_install_bootstrap_uses_override_list(
    tmp_path: Path, monkeypatch
) -> None:
    cfg = _config(tmp_path)
    cfg["AI_BOOTSTRAP_MODEL_LIST"] = "tinyllama:1.1b"
    monkeypatch.setattr(provisioning, "ensure_ollama_running", lambda **kwargs: True)
    monkeypatch.setattr(provisioning, "_list_installed_models", lambda config: [])
    monkeypatch.setattr(provisioning, "pull_ollama_model", lambda **kwargs: True)

    state = provisioning.run_first_install_bootstrap(cfg, force=True)
    models = [row["model"] for row in state.get("models", [])]
    assert models == ["tinyllama:1.1b"]


def test_run_first_install_bootstrap_uses_modelpack_when_pull_fails(
    tmp_path: Path, monkeypatch
) -> None:
    cfg = _config(tmp_path)
    cfg["AI_BOOTSTRAP_USE_MODELPACK"] = True
    cfg["AI_BOOTSTRAP_MODELPACK_FILE"] = str(tmp_path / "offline-pack.tar.gz")

    monkeypatch.setattr(provisioning, "ensure_ollama_running", lambda **kwargs: True)

    pull_attempts: list[str] = []

    def _pull(*, model: str, timeout_s: int = 0) -> bool:
        pull_attempts.append(model)
        return False

    monkeypatch.setattr(provisioning, "pull_ollama_model", _pull)

    imported = {"ok": False}

    def _import(**kwargs):
        imported["ok"] = True
        return {"ok": True, "pack_path": str(cfg["AI_BOOTSTRAP_MODELPACK_FILE"])}

    monkeypatch.setattr(provisioning, "import_model_pack", _import)

    def _installed_models(_config):
        if imported["ok"]:
            return ["llama3.2:3b", "llama3.1:8b", "qwen2.5:3b"]
        return []

    monkeypatch.setattr(provisioning, "_list_installed_models", _installed_models)

    Path(cfg["AI_BOOTSTRAP_MODELPACK_FILE"]).write_bytes(b"dummy")
    state = provisioning.run_first_install_bootstrap(cfg, force=True)

    assert state["status"] == "done"
    assert state["modelpack"]["attempted"] is True
    assert state["modelpack"]["imported"] is True
    assert state["models_ok"] is True
    assert pull_attempts == []
