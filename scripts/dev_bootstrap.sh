#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip -q install -U pip
python -m pip -q install -r requirements.txt

python3 scripts/seed_dev_users.py
python3 kukanilea_app.py
