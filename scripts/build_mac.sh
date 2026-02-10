#!/usr/bin/env bash
set -euo pipefail

APP_NAME="KUKANILEA"
ENTRYPOINT="kukanilea_app.py"

python3 -m pip install --upgrade pyinstaller

pyinstaller \
  --name "$APP_NAME" \
  --onefile \
  --windowed \
  "$ENTRYPOINT"

echo "Build complete: dist/${APP_NAME}.app"
