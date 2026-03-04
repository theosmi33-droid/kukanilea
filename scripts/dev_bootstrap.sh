#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

START_TS="$(date +%s)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate
python -m pip -q install -U pip
python -m pip -q install -r requirements.txt

python3 scripts/seed_dev_users.py
python3 scripts/seed_demo_data.py
python3 -m app.smoke

END_TS="$(date +%s)"
echo "✅ Bootstrap dry run complete in $((END_TS-START_TS))s"
