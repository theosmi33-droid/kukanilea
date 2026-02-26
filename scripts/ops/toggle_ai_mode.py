import json
import sys
from pathlib import Path

PROFILE_PATH = Path("instance/hardware_profile.json")

def set_mode(mode: str):
    if mode == "eco":
        model = "qwen2.5:0.5b"
        status = "ECO-MODE (Resource Saving)"
    elif mode == "performance":
        model = "llama3.1" # Or any larger model you have
        status = "PERFORMANCE-MODE (Full Power)"
    else:
        print("Usage: python toggle_ai_mode.py [eco|performance]")
        return

    profile = {
        "recommended_model": model,
        "status": status,
        "manual_override": True
    }

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)
    
    print(f"[OK] Switched to {status}")
    print(f"     Next AI request will use: {model}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python toggle_ai_mode.py [eco|performance]")
    else:
        set_mode(sys.argv[1].lower())
