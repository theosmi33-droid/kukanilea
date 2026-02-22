#!/usr/bin/env python3
import subprocess
import os
import sys
from pathlib import Path

def make_dmg():
    """
    Simulated DMG generation for macOS field test.
    Compliance: Distribution Trust.
    """
    print("--- KUKANILEA DMG GENERATOR ---")
    
    app_path = Path("dist/KUKANILEA.app")
    if not app_path.exists():
        print("[FAIL] KUKANILEA.app not found. Build first.")
        return False
        
    dmg_path = Path("dist/KUKANILEA_FieldTest.dmg")
    if dmg_path.exists():
        dmg_path.unlink()
        
    print(f"Creating Disk Image from {app_path}...")
    
    # Using hdiutil (native macOS)
    try:
        subprocess.run([
            "hdiutil", "create", 
            "-volname", "KUKANILEA_Setup", 
            "-srcfolder", str(app_path), 
            "-ov", "-format", "UDZO", 
            str(dmg_path)
        ], check=True)
        print(f"SUCCESS: DMG created at {dmg_path}")
        return True
    except Exception as e:
        print(f"FAILED: DMG creation failed: {e}")
        return False

if __name__ == "__main__":
    if sys.platform != "darwin":
        print("DMG creation only supported on macOS.")
        sys.exit(0)
    make_dmg()
