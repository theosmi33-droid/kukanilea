#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_NAME="KUKANILEA"
ENTRYPOINT="$ROOT_DIR/dist/_packaging_entrypoint.py"
OBF_PARENT="$ROOT_DIR/dist/obfuscated"
OBF_APP="$OBF_PARENT/app"

if [ "${1:-}" != "--skip-obfuscate" ]; then
  "$ROOT_DIR/scripts/build/obfuscate.sh"
fi

if [ ! -d "$OBF_APP" ]; then
  echo "Missing $OBF_APP. Run scripts/build/obfuscate.sh first." >&2
  exit 1
fi

if ! command -v pyinstaller >/dev/null 2>&1; then
  echo "pyinstaller not found. Install build tools first." >&2
  exit 1
fi

cat > "$ENTRYPOINT" <<'PY'
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(__file__)
OBF_PARENT = os.path.join(ROOT, "obfuscated")
if os.path.isdir(OBF_PARENT):
    sys.path.insert(0, OBF_PARENT)

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    from waitress import serve

    serve(app, host="127.0.0.1", port=int(os.environ.get("PORT", "5051")))
PY

rm -rf "$ROOT_DIR/build/$APP_NAME" "$ROOT_DIR/dist/$APP_NAME" "$ROOT_DIR/dist/$APP_NAME.app"

PYI_ARGS=(
  --noconfirm
  --clean
  --windowed
  --name "$APP_NAME"
  --paths "$OBF_PARENT"
  --add-data "$ROOT_DIR/templates:templates"
  --add-data "$ROOT_DIR/static:static"
)

if [ -f "$ROOT_DIR/assets/icon.icns" ]; then
  PYI_ARGS+=(--icon "$ROOT_DIR/assets/icon.icns")
fi

PYI_ARGS+=("$ENTRYPOINT")

pyinstaller "${PYI_ARGS[@]}"

echo "Bundle ready: $ROOT_DIR/dist/$APP_NAME.app"
