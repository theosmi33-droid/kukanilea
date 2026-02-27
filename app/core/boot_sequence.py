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
        # Check if llmfit is in PATH
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

    # Fallback for old/limited hardware
    return "qwen2.5:0.5b"


def run_boot_sequence():
    """
    Initializes the system:
    1. Integrity check (v2.1 Step 1).
    2. Detects hardware via llmfit.
    3. Saves the profile.
    4. Pulls the recommended model via Ollama if needed.
    """
    from app.core.integrity_check import check_system_integrity
    
    # 1. Integrity Check
    print("System Integrity Check (v2.1)...")
    integrity = check_system_integrity()
    if not integrity.get("all_ok", False):
        if os.environ.get("KUK_SAFE_MODE") == "1":
            print("⚠️ WARNING: Integrity failed, but running in SAFE MODE.")
        else:
            print("❌ CRITICAL: Integrity check failed! Boot aborted.")
            print("Check logs/crash/ for details.")
            return False

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

    # Optional: Auto-pull model if connected to internet
    try:
        response = requests.post(
            "http://localhost:11434/api/pull",
            json={"name": model, "stream": False},
            timeout=5,
        )
        if response.status_code == 200:
            print(f"Model {model} is ready.")
    except Exception:
        print(f"Ollama not reachable or offline. Skipping auto-pull for {model}.")


if __name__ == "__main__":
    run_boot_sequence()
