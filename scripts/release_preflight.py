#!/usr/bin/env python3
import os
import subprocess
import sys
import platform

def run_step(name, command):
    print(f"[*] Step: {name}...", end="", flush=True)
    try:
        env = os.environ.copy()
        env["PYENV_VERSION"] = "3.14.2"
        res = subprocess.run(command, capture_output=True, text=True, timeout=60, env=env)
        if res.returncode == 0:
            print(" [PASS]")
            return True
        else:
            print(" [FAIL]")
            print(f"\nERROR in {name}:\n{res.stderr or res.stdout}")
            return False
    except Exception as e:
        print(f" [ERROR] {e}")
        return False

def main():
    print("=== KUKANILEA RC1 PRE-FLIGHT CHECK ===\n")
    
    python_bin = "/Users/gensuminguyen/.pyenv/shims/python3.14"
    pytest_bin = "/Users/gensuminguyen/.pyenv/shims/pytest"
    
    # Check OS
    print(f"[INFO] OS: {platform.system()} {platform.release()}")
    print(f"[INFO] Python: {python_bin}")
    
    # Steps
    steps = [
        ("Check Assets (Icon)", ["ls", "assets/icon.ico"]),
        ("Security Tests (Salted Inference)", [pytest_bin, "-W", "ignore", "tests/security/test_salted_inference.py"]),
        ("SBOM Generation", [python_bin, "scripts/generate_sbom.py"]),
    ]
    
    all_pass = True
    for name, cmd in steps:
        if not run_step(name, cmd):
            all_pass = False
            break
            
    if all_pass:
        print("\n[SUCCESS] KUKANILEA is ready for RC1 release!")
        sys.exit(0)
    else:
        print("\n[FAIL] Pre-flight checks failed. Please fix the issues before release.")
        sys.exit(1)

if __name__ == "__main__":
    main()
