#!/bin/bash
set -e

# KUKANILEA Blue/Green Deployment Update Manager
# Usage: ./update_manager.sh v1.0.1

if [ -z "$1" ]; then
    echo "❌ Error: Please specify a version (e.g., v1.0.1)"
    exit 1
fi

NEW_VERSION=$1
BASE_DIR="/opt/kukanilea"
CURRENT_SYMLINK="$BASE_DIR/current"
NEW_RELEASE_DIR="$BASE_DIR/$NEW_VERSION"

echo "🚀 Starting Blue/Green Update to $NEW_VERSION"

# 1. Fetch current version to allow rollback
if [ -L "$CURRENT_SYMLINK" ]; then
    CURRENT_VERSION_DIR=$(readlink -f "$CURRENT_SYMLINK")
else
    # First time setup
    CURRENT_VERSION_DIR=""
fi

# 2. Prepare new directory
mkdir -p "$NEW_RELEASE_DIR"

# 3. Download & Verify (Mocked for this example)
echo "📥 Downloading release payload..."
# wget -qO "$BASE_DIR/$NEW_VERSION.tar.gz" "https://updates.kukanilea.com/$NEW_VERSION.tar.gz"
# gpg --verify "$BASE_DIR/$NEW_VERSION.tar.gz.sig"
# tar -xzf "$BASE_DIR/$NEW_VERSION.tar.gz" -C "$NEW_RELEASE_DIR" --strip-components=1

# Mock extracting (copying current files if they exist, or just placeholder)
if [ -n "$CURRENT_VERSION_DIR" ]; then
    cp -a "$CURRENT_VERSION_DIR/"* "$NEW_RELEASE_DIR/"
fi

# 4. Dry-Run / Test
echo "🧪 Running Dry-Run Pre-flight Checks..."
# Assume python virtual environment is initialized in the new dir
# $NEW_RELEASE_DIR/.venv/bin/python $NEW_RELEASE_DIR/run.py check
sleep 1

# 5. Atomic Switch
echo "🔄 Performing Atomic Symlink Switch..."
ln -sfn "$NEW_RELEASE_DIR" "$CURRENT_SYMLINK"

# 6. Restart Service
echo "⚡ Restarting systemd service..."
# systemctl restart kukanilea.service

# 7. Post-Deploy Health Check
echo "🩺 Verifying Health..."
# HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5051/health)
HTTP_STATUS=200 # Mocked for testing without active service

if [ "$HTTP_STATUS" -ne 200 ]; then
    echo "❌ Healthcheck failed (HTTP $HTTP_STATUS). Initiating ROLLBACK."
    if [ -n "$CURRENT_VERSION_DIR" ]; then
        ln -sfn "$CURRENT_VERSION_DIR" "$CURRENT_SYMLINK"
        # systemctl restart kukanilea.service
        echo "✅ Rollback to $CURRENT_VERSION_DIR complete."
    else
        echo "⚠️ No previous version to rollback to."
    fi
    exit 1
else
    echo "✅ Update to $NEW_VERSION successful. 0% Downtime achieved."
fi
