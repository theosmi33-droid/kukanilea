#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="KUKANILEA"
ENTRYPOINT="$ROOT_DIR/run.py"

PY_BIN="${PYTHON:-python3}"

echo "📦 Installing build dependencies..."
"$PY_BIN" -m pip install --upgrade pyinstaller waitress platformdirs cryptography pydantic requests python-dotenv

echo "🏗️ Starting PyInstaller Build..."
pyinstaller \
  --noconfirm \
  --clean \
  --name "$APP_NAME" \
  --onefile \
  --windowed \
  --icon "$ROOT_DIR/assets/icon.icns" \
  --add-data "$ROOT_DIR/app/agents:app/agents" \
  --add-data "$ROOT_DIR/app/auth.py:app" \
  --add-data "$ROOT_DIR/app/config.py:app" \
  --add-data "$ROOT_DIR/app/core:app/core" \
  --add-data "$ROOT_DIR/app/db.py:app" \
  --add-data "$ROOT_DIR/app/errors.py:app" \
  --add-data "$ROOT_DIR/app/lifecycle.py:app" \
  --add-data "$ROOT_DIR/app/static:app/static" \
  --add-data "$ROOT_DIR/app/web.py:app" \
  --add-data "$ROOT_DIR/app/__init__.py:app" \
  "$ENTRYPOINT"

echo "✅ Build complete: $ROOT_DIR/dist/${APP_NAME}.app"
