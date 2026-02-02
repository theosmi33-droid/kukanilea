#!/usr/bin/env bash
set -euo pipefail

# Install Ollama via Homebrew (macOS):
#   brew install ollama
# Start daemon:
#   ollama serve
# Pull model once:
#   ollama pull llama3.1

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama not found. Install with: brew install ollama"
  exit 1
fi

# start background server if not listening
if ! lsof -i :11434 >/dev/null 2>&1; then
  nohup ollama serve >/tmp/ollama_serve.log 2>&1 &
  sleep 1
fi

ollama pull llama3.1
echo "Ollama ready on http://127.0.0.1:11434"
