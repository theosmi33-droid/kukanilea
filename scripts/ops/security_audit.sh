#!/bin/bash
# KUKANILEA Security Audit Script
# Purpose: Detect vulnerable dependencies and static code flaws.

set -e

echo "[$(date -u)] Starting KUKANILEA Security Audit..."

# 1. Dependency Audit
if command -v pip-audit &> /dev/null; then
    echo "Running pip-audit..."
    pip-audit -r requirements.txt
else
    echo "[SKIP] pip-audit not found. Install with: pip install pip-audit"
fi

# 2. Static Code Analysis (Bandit)
if command -v bandit &> /dev/null; then
    echo "Running bandit..."
    bandit -r app/ kukanilea/ -lll
else
    echo "[SKIP] bandit not found. Install with: pip install bandit"
fi

# 3. Secret Scan (Simplified)
echo "Scanning for potential hardcoded secrets..."
grep -rnE "SECRET|KEY|PASSWORD|TOKEN" app/ | grep -vE "\.env|Config\.|class|def|@|_env" || echo "No obvious secrets found."

echo "[$(date -u)] Security Audit complete."
