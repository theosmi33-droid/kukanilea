import os
import sys
import json

def check_mac_creds():
    """Checks for Apple Developer ID / Notary credentials."""
    return os.environ.get("APPLE_ID") is not None and os.environ.get("APPLE_PASSWORD") is not None

def check_win_sdk():
    """Checks for Windows SignTool and Certificates."""
    # Simplified check for local SDK presence
    return os.name == 'nt' and os.environ.get("WIN_CERT_THUMBPRINT") is not None

def main():
    status = {
        "D-MAC": "PASS" if check_mac_creds() else "BLOCKED",
        "D-WIN": "PASS" if check_win_sdk() else "BLOCKED"
    }
    
    os.makedirs("output/distribution", exist_ok=True)
    with open("output/distribution/gate_status_local.json", "w") as f:
        json.dump(status, f, indent=4)
    
    print("--- Distribution Gate Audit ---")
    for gate, state in status.items():
        print(f"{gate}: {state}")

if __name__ == "__main__":
    main()
