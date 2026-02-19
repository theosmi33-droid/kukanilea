#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "== KUKANILEA Beta Quickstart =="

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if command -v ollama >/dev/null 2>&1; then
  if curl -sSf "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    echo "Ollama erreichbar: KI-Funktionen aktiv."
  else
    echo "Hinweis: Ollama installiert, aber nicht gestartet (ollama serve)."
  fi
else
  echo "Hinweis: Ollama nicht installiert. KI-Funktionen bleiben deaktiviert."
fi

exec python kukanilea_app.py
