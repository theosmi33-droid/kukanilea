#!/usr/bin/env python3
"""
scripts/ops/security_scan.py
KUKANILEA SUPPLY-CHAIN SECURITY AUDIT
Scans requirements.txt for known vulnerabilities using pip-audit.
Integrated into the Maintenance Daemon and Global Health Monitor.
"""

import json
import logging
import sqlite3
import subprocess
import sys
from pathlib import Path

# Projekt-Pfad hinzufügen
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Logger-Setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("kukanilea.security")

# Pfade
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
CONFIG_FILE = PROJECT_ROOT / "instance" / "config.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "instance" / "kukanilea.db"


def get_db_path():
    """Returns the current database path from config or default."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                custom_path = data.get("database_path")
                if custom_path:
                    return Path(custom_path) / "kukanilea.db"
        except Exception:
            pass
    return DEFAULT_DB_PATH


def run_pip_audit():
    """Runs pip-audit and returns the exit code and output."""
    logger.info(f"Starting pip-audit for {REQUIREMENTS_FILE}...")
    try:
        # Use json format to parse vulnerabilities easily
        result = subprocess.run(
            ["pip-audit", "-r", str(REQUIREMENTS_FILE), "--format", "json"],
            capture_output=True,
            text=True,
            check=False,  # We handle return code ourselves
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        logger.error(
            "pip-audit not found. Please install it with 'pip install pip-audit'."
        )
        return 127, "", "pip-audit not found"


def notify_security_issue(vuln_count, vuln_details):
    """Inserts a security alert into the agent_notifications table."""
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        message = f"[SECURITY CRITICAL] {vuln_count} vulnerabilities found in dependencies! See security logs for details."
        action_json = json.dumps({"type": "security_audit", "details": vuln_details})

        cursor.execute(
            "INSERT INTO agent_notifications (tenant_id, role, message, action_json, status) VALUES (?, ?, ?, ?, ?)",
            ("SYSTEM", "SECURITY", message, action_json, "new"),
        )
        conn.commit()
        conn.close()
        logger.info("Security alert inserted into database.")
    except Exception as e:
        logger.error(f"Failed to insert security alert: {e}")


def main():
    if not REQUIREMENTS_FILE.exists():
        logger.error(f"Requirements file not found: {REQUIREMENTS_FILE}")
        sys.exit(1)

    return_code, stdout, stderr = run_pip_audit()

    if return_code == 0:
        logger.info("Supply-Chain Audit: PASS. No vulnerabilities found.")
        sys.exit(0)
    else:
        # Try to parse json output
        try:
            vulns = json.loads(stdout)
            # pip-audit returns vulnerabilities in dependencies
            # We want to filter for Critical/High if possible, but pip-audit
            # doesn't always provide severity in the standard json output easily
            # without --osv or other flags.
            # However, any vulnerability in Enterprise should be treated as high.

            # Count vulnerabilities
            vuln_count = 0
            if isinstance(vulns, list):
                # Standard json format: List of objects with 'name', 'version', 'vulnerabilities'
                for item in vulns:
                    vuln_count += len(item.get("vulnerabilities", []))
            elif isinstance(vulns, dict) and "dependencies" in vulns:
                # Some versions/formats might differ
                for dep in vulns["dependencies"]:
                    vuln_count += len(dep.get("vulnerabilities", []))

            logger.error(
                f"Supply-Chain Audit: FAIL. Found {vuln_count} vulnerabilities."
            )

            # Create a summary for details
            vuln_summary = stdout[:2000]  # Limit size for DB
            notify_security_issue(vuln_count, vuln_summary)

            # Print for logs
            print(stdout)

            sys.exit(1)  # Fail the build/maintenance
        except json.JSONDecodeError:
            logger.error("Failed to parse pip-audit output.")
            if stderr:
                logger.error(f"pip-audit error: {stderr}")
            sys.exit(1)


if __name__ == "__main__":
    main()
