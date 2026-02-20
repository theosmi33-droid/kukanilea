#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_DIR="$ROOT_DIR/app"
OUT_ROOT="$ROOT_DIR/dist/obfuscated"
OUT_DIR="$OUT_ROOT/app"

mkdir -p "$OUT_ROOT"
rm -rf "$OUT_DIR"

if [ ! -d "$SRC_DIR" ]; then
  echo "Missing source directory: $SRC_DIR" >&2
  exit 1
fi

copy_fallback() {
  rm -rf "$OUT_DIR"
  cp -R "$SRC_DIR" "$OUT_DIR"
  echo "Copied source to: $OUT_DIR"
}

if command -v pyarmor >/dev/null 2>&1; then
  echo "Obfuscating app/ with PyArmor..."
  if pyarmor gen --recursive --output "$OUT_DIR" "$SRC_DIR"; then
    echo "Obfuscation output: $OUT_DIR"
  else
    echo "PyArmor failed (likely trial/license/runtime issue). Falling back to plain copy (no obfuscation)." >&2
    copy_fallback
  fi
else
  echo "PyArmor not found. Falling back to plain copy (no obfuscation)."
  copy_fallback
fi
