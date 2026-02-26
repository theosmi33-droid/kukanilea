#!/usr/bin/env bash
# scripts/ops/build_release.sh
# Final Polish & Release Packaging for ZimaBlade (Linux/General)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../" && pwd)"
VERSION="1.7.0"
RELEASE_NAME="kukanilea-v${VERSION}-zimablade"
DIST_DIR="$PROJECT_ROOT/dist"
STAGING_DIR="$DIST_DIR/$RELEASE_NAME"

echo "🧹 Cleaning environment..."
cd "$PROJECT_ROOT"
find . -type d -name "__pycache__" -exec rm -rf {} +
rm -rf "$STAGING_DIR"
rm -f "$DIST_DIR/${RELEASE_NAME}.tar.gz"

echo "🕵️ Running security audit..."
pip-audit -r requirements.txt

echo "🏗️ Preparing Staging Area..."
mkdir -p "$STAGING_DIR"

# Copy essential files
cp -R app "$STAGING_DIR/"
cp -R scripts "$STAGING_DIR/"
cp run.py "$STAGING_DIR/"
cp requirements.txt "$STAGING_DIR/"
cp pyproject.toml "$STAGING_DIR/"
cp README.md "$STAGING_DIR/"
cp ROADMAP.md "$STAGING_DIR/"

# Remove dev/test files from staging
rm -rf "$STAGING_DIR/app/tests"
rm -rf "$STAGING_DIR/scripts/tests"
find "$STAGING_DIR" -name "test_*.py" -delete

echo "📦 Creating Tarball..."
cd "$DIST_DIR"
tar -czf "${RELEASE_NAME}.tar.gz" "$RELEASE_NAME"

echo "✅ Release Package Ready: $DIST_DIR/${RELEASE_NAME}.tar.gz"
echo "Target: ZimaBlade (Linux)"
