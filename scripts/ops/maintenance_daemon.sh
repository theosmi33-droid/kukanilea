#!/bin/bash
# KUKANILEA Maintenance Daemon
# Purpose: Preventive Maintenance, Supply-Chain Security Audit, and Health Check.
# Schedule: Run via crontab at 03:00 daily or as part of the CI/CD pipeline.

set -e

# Base Path setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../" && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv"

# Ensure we are in the project root
cd "$PROJECT_ROOT"

echo "[$(date -u)] Starting Maintenance..."

# 1. Supply-Chain Security Scan (Critical)
# ----------------------------------------
echo "[$(date -u)] Running Supply-Chain Security Scan..."
if [ -f "$VENV_PATH/bin/python" ]; then
    "$VENV_PATH/bin/python" "$PROJECT_ROOT/scripts/ops/security_scan.py"
else
    python3 "$PROJECT_ROOT/scripts/ops/security_scan.py"
fi

# 2. Database Maintenance (Vacuum)
# --------------------------------
echo "[$(date -u)] Running DB Maintenance..."
DB_PATH="$PROJECT_ROOT/instance/kukanilea.db"
if [ -f "$DB_PATH" ]; then
    echo "Vacuuming $DB_PATH..."
    sqlite3 "$DB_PATH" "VACUUM;"
fi

# 3. Cleanup temporary assets
# ---------------------------
TMP_DIR="$PROJECT_ROOT/tmp"
if [ -d "$TMP_DIR" ]; then
    echo "Cleaning up temp files older than 7 days..."
    find "$TMP_DIR" -type f -mtime +7 -delete
fi

# 4. Core-Dependency Advisor (Dev/Ops)
# ------------------------------------
echo "[$(date -u)] Checking for core dependency updates..."
if [ -f "$VENV_PATH/bin/python" ]; then
    "$VENV_PATH/bin/python" "$PROJECT_ROOT/scripts/dev/check_updates.py"
else
    python3 "$PROJECT_ROOT/scripts/dev/check_updates.py"
fi

# 5. Weekly Chaos Monkey (Every Sunday)
# -------------------------------------
DAY_OF_WEEK=$(date +%u) # 1-7, 7 ist Sonntag
if [ "$DAY_OF_WEEK" -eq 7 ]; then
    echo "[$(date -u)] Sunday detected. Starting Weekly CHAOS MONKEY..."
    if [ -f "$VENV_PATH/bin/python" ]; then
        "$VENV_PATH/bin/python" "$PROJECT_ROOT/scripts/tests/chaos_monkey.py"
    else
        python3 "$PROJECT_ROOT/scripts/tests/chaos_monkey.py"
    fi
fi

echo "[$(date -u)] Maintenance complete."
