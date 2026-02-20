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

if __name__ == "__main__":
    from app.desktop import main

    raise SystemExit(main())
PY

rm -rf "$ROOT_DIR/build/$APP_NAME" "$ROOT_DIR/dist/$APP_NAME" "$ROOT_DIR/dist/$APP_NAME.app"

PYI_ARGS=(
  --noconfirm
  --clean
  --windowed
  --name "$APP_NAME"
  --paths "$OBF_PARENT"
  --paths "$ROOT_DIR"
  --hidden-import kukanilea_core_v3_fixed
  --hidden-import webview
  --hidden-import webview.platforms.cocoa
  --add-data "$ROOT_DIR/templates:templates"
  --add-data "$ROOT_DIR/static:static"
)

if [ -f "$ROOT_DIR/assets/icon.icns" ]; then
  PYI_ARGS+=(--icon "$ROOT_DIR/assets/icon.icns")
fi

PYI_ARGS+=("$ENTRYPOINT")

pyinstaller "${PYI_ARGS[@]}"

echo "Bundle ready: $ROOT_DIR/dist/$APP_NAME.app"
