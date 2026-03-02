import json
import os
import subprocess
from pathlib import Path

import requests


def get_optimal_llm(use_case="general"):
    """
    Calls 'llmfit' to get the best model recommendation for the current hardware.
    Fallbacks to a very small model if llmfit is missing or fails.
    """
    import platform

    binary = "llmfit.exe" if platform.system() == "Windows" else "llmfit"
    try:
        result = subprocess.run(
            [binary, "recommend", "--json", "--use-case", use_case, "--limit", "1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data and len(data) > 0:
                return data[0]["name"]
    except Exception as e:
        print(f"llmfit error or missing: {e}")

    return "qwen2.5:0.5b"


def _model_installed(installed: list[str], required: str) -> bool:
    for name in installed:
        if name == required or name.startswith(required + ":"):
            return True
    return False


def _ensure_ollama_models(required_models: list[str]) -> None:
    """
    Ensures required local models are present in Ollama.
    Never uses cloud APIs; only local Ollama endpoint.

    Default behavior is non-blocking: report missing models only.
    Enable auto pull with KUK_OLLAMA_AUTOPULL=1.
    """
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    auto_pull = os.environ.get("KUK_OLLAMA_AUTOPULL", "0") == "1"
    pull_timeout = int(os.environ.get("KUK_OLLAMA_PULL_TIMEOUT", "120"))

    try:
        tags = requests.get(f"{base}/api/tags", timeout=4)
        tags.raise_for_status()
        payload = tags.json() or {}
        installed = [m.get("name", "") for m in payload.get("models", [])]
    except Exception as e:
        print(f"Ollama not reachable ({e}). Skipping model preflight.")
        return

    missing = [m for m in required_models if not _model_installed(installed, m)]
    if not missing:
        print("Ollama preflight OK: required models available.")
        return

    print(f"Ollama preflight: missing models: {', '.join(missing)}")
    if not auto_pull:
        print("Auto-pull disabled (set KUK_OLLAMA_AUTOPULL=1 to pull automatically).")
        return

    print(f"Ollama preflight: pulling missing models: {', '.join(missing)}")
    for model_name in missing:
        try:
            response = requests.post(
                f"{base}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=pull_timeout,
            )
            response.raise_for_status()
            print(f"Model {model_name} is ready.")
        except Exception as e:
            print(f"Failed to pull model {model_name}: {e}")


def run_boot_sequence():
    """
    Initializes the system:
    1. Integrity check (v2.1 Step 1).
    2. Detects hardware via llmfit.
    3. Saves the profile.
    4. Ensures local Ollama models are available.
    """
    from app.core.integrity_check import check_system_integrity

    print("System Integrity Check (v2.1)...")
    integrity = check_system_integrity()
    if not integrity.get("all_ok", False):
        if os.environ.get("KUK_SAFE_MODE") == "1":
            print("⚠️ WARNING: Integrity failed, but running in SAFE MODE.")
        else:
            print("❌ CRITICAL: Integrity check failed! Boot aborted.")
            print("Check logs/crash/ for details.")
            return False

    # 1.1 Auto-Evolution (Task 201)
    from app.core.auto_evolution import SystemHealer
    from app.core.rag_sync import RAGSync
    from app.core.migrations import repair_legacy_customer_fk
    from app.config import Config

    try:
        repaired = repair_legacy_customer_fk(Config.CORE_DB)
        if repaired:
            print("Legacy FK schema repaired (customers.id).")
    except Exception as e:
        print(f"Legacy FK repair failed: {e}")

    print("Auto-Evolution & RAG-SYNC (v2.5)...")
    healer = SystemHealer(Config.CORE_DB, Config.BASE_DIR)
    healer.run_healing_cycle()
    healer.evolution_step()

    try:
        memory_file = Path("MEMORY.md")
        rag = RAGSync(Config.CORE_DB, memory_file)
        rag.sync_tenant_intelligence(os.environ.get("TENANT_DEFAULT", "KUKANILEA"))
    except Exception as e:
        print(f"RAG-SYNC failed: {e}")

    profile_path = Path("instance/hardware_profile.json")
    profile_path.parent.mkdir(parents=True, exist_ok=True)

    model = get_optimal_llm()
    profile = {
        "recommended_model": model,
        "boot_ts": os.path.getmtime(__file__) if os.path.exists(__file__) else 0,
    }

    with open(profile_path, "w") as f:
        json.dump(profile, f)

    print(f"Hardware-Aware Boot: Recommended model is {model}")

    required_models = ["nomic-embed-text", "qwen2.5:0.5b"]
    if model not in required_models:
        required_models.append(model)
    _ensure_ollama_models(required_models)


if __name__ == "__main__":
    run_boot_sequence()
