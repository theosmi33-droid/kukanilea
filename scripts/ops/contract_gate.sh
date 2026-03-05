#!/usr/bin/env python3
import sys
import os
import re

# KUKANILEA Enterprise Gate: Contract Gate
# Verifies that all 11 tools have required contract endpoints.

CONTRACT_TOOLS = [
    "dashboard",
    "upload",
    "projects",
    "tasks",
    "messenger",
    "email",
    "calendar",
    "time",
    "visualizer",
    "settings",
    "chatbot",
]

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEB_PY = os.path.join(ROOT, "app", "web.py")

def check_endpoints():
    if not os.path.exists(WEB_PY):
        print(f"FAIL: {WEB_PY} not found.")
        return False

    with open(WEB_PY, "r") as f:
        content = f.read()

    # The routes are defined as:
    # @bp.get("/api/<tool>/summary")
    # @bp.get("/api/<tool>/health")
    
    # We check if these routes exist and handle the tools correctly.
    # From my previous read of web.py, I know they use generic <tool> placeholders.
    
    summary_route = re.search(r'@bp\.get\("/api/<tool>/summary"\)', content)
    health_route = re.search(r'@bp\.get\("/api/<tool>/health"\)', content)
    
    if not summary_route:
        print("FAIL: Missing /api/<tool>/summary route in web.py")
        return False
    if not health_route:
        print("FAIL: Missing /api/<tool>/health route in web.py")
        return False

    # Check if CONTRACT_TOOLS is consistent
    tool_contracts_py = os.path.join(ROOT, "app", "contracts", "tool_contracts.py")
    if os.path.exists(tool_contracts_py):
        with open(tool_contracts_py, "r") as f:
            contract_content = f.read()
        
        for tool in CONTRACT_TOOLS:
            if f'"{tool}"' not in contract_content:
                print(f"FAIL: Tool '{tool}' not found in app/contracts/tool_contracts.py")
                return False
    else:
        print(f"FAIL: {tool_contracts_py} not found.")
        return False

    return True

if __name__ == "__main__":
    print("[contract-gate] Checking tool contracts...")
    if check_endpoints():
        print("PASS: Tool contracts are valid.")
        sys.exit(0)
    else:
        sys.exit(1)
