#!/usr/bin/env bash
set -euo pipefail

# KUKANILEA UI Start (macOS / zsh/bash)
# Requirements: python3, venv, Ollama installed (optional for chat)

cd "$(dirname "$0")/.."

# venv
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip -q install -U pip
pip -q install -r requirements.txt

# Ollama (optional): auto-start enabled in app if env var set
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export KUKANILEA_OLLAMA_MODEL="${KUKANILEA_OLLAMA_MODEL:-llama3.1}"
export KUKANILEA_AUTO_START_OLLAMA="${KUKANILEA_AUTO_START_OLLAMA:-1}"

python3 kukanilea_app.py
