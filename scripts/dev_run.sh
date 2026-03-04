#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASE_PYTHON="$(scripts/dev/resolve_python.sh)"

if [[ ! -d ".venv" ]]; then
  "$BASE_PYTHON" -m venv .venv
fi

PYTHON="$ROOT/.venv/bin/python"
"$PYTHON" -m pip -q install -U pip
"$PYTHON" -m pip -q install -r requirements.txt

"$PYTHON" scripts/seed_dev_users.py
"$PYTHON" kukanilea_app.py
