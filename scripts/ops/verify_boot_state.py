import sys
from pathlib import Path
from flask import Flask

# Mock app setup to read config
sys.path.append(str(Path(__file__).parent.parent.parent))
from app import create_app

def verify():
    print("--- KUKANILEA Final DRM Audit ---")
    app = create_app()
    plan = app.config.get("PLAN", "UNKNOWN")
    read_only = app.config.get("READ_ONLY", True)
    reason = app.config.get("LICENSE_REASON", "no_info")
    
    print(f"Current Plan: {plan}")
    print(f"Read Only: {read_only}")
    print(f"License Reason: {reason}")
    
    if plan == "ENTERPRISE" and not read_only:
        print("\n[AUDIT PASSED] DRM Pipeline is robust. System is Enterprise-Active.")
    else:
        print("\n[AUDIT FAILED] System did not reach Enterprise-Active state.")
        sys.exit(1)

if __name__ == "__main__":
    verify()
