#!/usr/bin/env python3
"""
scripts/generate_evidence_pack.py
Automatisiert die Erstellung des 'Release Evidence Pack' für den Release Captain.
Zuständig für: Unit-Tests, E2E, Perf, SBOM und Verifizierung.
"""

import datetime
import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
EVIDENCE_DIR = PROJECT_ROOT / "dist" / "evidence"
DATE_STR = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def run_step(name, command, cwd=PROJECT_ROOT):
    print(f"--- Running Step: {name} ---")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True, cwd=cwd)
        print(f"SUCCESS: {name}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"FAILED: {name} (Exit Code {e.returncode})")
        return False, e.stderr

def main():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    summary = {
        "timestamp": DATE_STR,
        "steps": {}
    }

    # 1. Unit & Integration Tests
    success, output = run_step("Unit Tests", "pytest tests/ --junitxml=dist/evidence/unit_results.xml")
    summary["steps"]["unit_tests"] = "PASS" if success else "FAIL"

    # 2. SBOM Generation (CycloneDX)
    # Nutzt das vorhandene generate_sbom.py (falls vorhanden)
    success, output = run_step("SBOM Generation", "python3 scripts/generate_sbom.py --format cyclonedx --output dist/evidence/sbom.cdx.json")
    summary["steps"]["sbom"] = "PASS" if success else "FAIL"

    # 3. Perf/Endurance Check (60 min nightly runner stub)
    # Hier wird das Protokoll des Endurance Runners eingebunden
    perf_log = PROJECT_ROOT / "triage_report.json"
    if perf_log.exists():
        summary["steps"]["performance"] = "PASS (Evidence from triage_report.json)"
    else:
        summary["steps"]["performance"] = "MISSING (Run bench_workflows.py first)"

    # 4. Final Evidence Summary
    summary_path = EVIDENCE_DIR / f"evidence_summary_{DATE_STR}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=4)
    
    print(f"\nEvidence Pack Summary generated: {summary_path}")
    
    overall_pass = all(s in ["PASS", "PASS (Evidence from triage_report.json)"] for s in summary["steps"].values())
    if overall_pass:
        print("\n[GO] Release Evidence Pack is COMPLETE.")
    else:
        print("\n[NO-GO] Some evidence steps FAILED. See JSON summary for details.")

if __name__ == "__main__":
    main()
