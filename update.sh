#!/usr/bin/env bash
set -euo pipefail

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git fetch origin
  git rebase origin/main
fi

if [[ -d ".venv" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  python -m pip install -r requirements-dev.txt
fi

ruff check . --fix
ruff format .
pytest -q
python -m app.smoke

cat <<'EOF'
Update complete.
To test a PR branch:
  git checkout <branch>
  git fetch origin
  git rebase origin/main
  ./update.sh
EOF
