#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="KUKANILEA"
ENTRYPOINT="$ROOT_DIR/run.py"

PY_BIN="${PYTHON:-python3}"

"$PY_BIN" -m pip install --upgrade pyinstaller waitress platformdirs cryptography

pyinstaller \
  --noconfirm \
  --clean \
  --name "$APP_NAME" \
  --onefile \
  --windowed \
  --add-data "$ROOT_DIR/app/core:app/core" \
  --add-data "$ROOT_DIR/app/observability:app/observability" \
  --add-data "$ROOT_DIR/app/static:app/static" \
  "$ENTRYPOINT"

echo "Build complete: $ROOT_DIR/dist/${APP_NAME}.app"
