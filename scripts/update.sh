#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Fetching latest from origin"
git fetch origin

echo "==> Switching to main"
git checkout main

echo "==> Rebasing onto origin/main"
git pull --rebase --autostash origin main

if [ ! -d ".venv" ]; then
  echo "==> Creating virtualenv (.venv)"
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -U pip
  if [ -f "requirements-dev.txt" ]; then
    python -m pip install -r requirements-dev.txt
  elif [ -f "requirements.txt" ]; then
    python -m pip install -r requirements.txt
  fi
else
  echo "==> Activating virtualenv (.venv)"
  source .venv/bin/activate
fi

echo "==> Running format + lint"
python -m ruff format .
python -m ruff check . --fix

echo "==> Running tests"
pytest -q
python -m app.smoke

echo "==> Update complete"
