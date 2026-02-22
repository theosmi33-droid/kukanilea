import json
import os
import sys
from pathlib import Path

def run_release_captain(mode="beta"):
    """
    Final Release Captain Orchestrator.
    Compliance: Evidence-driven Release Trust.
    """
    print(f"--- KUKANILEA RELEASE CAPTAIN (Mode: {mode.upper()}) ---")
    
    evidence_summary_path = Path("dist/evidence/gate_summary.json")
    if not evidence_summary_path.exists():
        print("[FAIL] No evidence summary found. Run 'scripts/build_evidence.py' first.")
        sys.exit(1)
        
    with open(evidence_summary_path, "r") as f:
        data = json.load(f)
        gates = data.get("gates", {})

    print("
Auditing Gates for Production Readiness:")
    failed_gates = []
    blocked_gates = []
    
    for gate, status in gates.items():
        print(f" - {gate}: {status}")
        if status == "FAIL":
            failed_gates.append(gate)
        if status == "BLOCKED":
            blocked_gates.append(gate)

    if failed_gates:
        print(f"
[NO-GO] release FAILED due to Quality violations: {failed_gates}")
        sys.exit(1)

    if mode == "strict" or mode == "prod":
        if blocked_gates:
            print(f"
[STRICT NO-GO] Production release BLOCKED by missing prerequisites: {blocked_gates}")
            print("Action: Resolve macOS/Windows signing credentials before final RC.")
            sys.exit(1)
            
    print("
[GO] Release evidence verified. Preparing final artifacts...")
    # Logic for tagging and packaging would go here.

if __name__ == "__main__":
    mode = "beta"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx+1]
    run_release_captain(mode)
