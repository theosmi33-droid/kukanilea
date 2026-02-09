#!/usr/bin/env bash
set -euo pipefail

git fetch origin
git checkout main
git rebase origin/main

ruff format .
ruff check . --fix
pytest -q
python -m app.smoke
