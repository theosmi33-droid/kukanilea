#!/usr/bin/env bash
set -euo pipefail

# KUKANILEA UI Start (macOS / zsh/bash)
# Requirements: python3 + venv

cd "$(dirname "$0")/.."

# venv
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip -q install -U pip
pip -q install -r requirements.txt

python3 run.py
