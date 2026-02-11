#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
DATE="$(date +%Y%m%d)"
REV="$(git -C "$ROOT_DIR" rev-parse --short HEAD)"
ZIP_NAME="kukanilea_mvp_${DATE}_${REV}.zip"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"
SHA_PATH="$ZIP_PATH.sha256"

STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

mkdir -p "$DIST_DIR" "$STAGE_DIR/kukanilea"

rsync -a \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.build_venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '__MACOSX/' \
  --exclude '*.DS_Store' \
  --exclude 'build/' \
  --exclude 'dist/' \
  --exclude 'instance/*.db*' \
  --exclude 'nousage/' \
  --exclude 'reports/' \
  --exclude 'scripts/start_ui.sh' \
  --exclude 'scripts/dev_*' \
  --exclude 'scripts/run_dev.sh' \
  --exclude 'scripts/ollama_bootstrap.sh' \
  "$ROOT_DIR/" "$STAGE_DIR/kukanilea/"

rm -f "$ZIP_PATH" "$SHA_PATH"
(
  cd "$STAGE_DIR"
  zip -rq "$ZIP_PATH" "kukanilea"
)

SHA_VALUE="$(shasum -a 256 "$ZIP_PATH" | awk '{print $1}')"
printf '%s  %s\n' "$SHA_VALUE" "$(basename "$ZIP_PATH")" > "$SHA_PATH"

echo "zip=$ZIP_PATH"
echo "sha256=$SHA_PATH"
