#!/bin/bash
# KUKANILEA Maintenance Daemon
# Purpose: Prevent DB fragmentation and clean up temporary assets.
# Schedule: Run via crontab at 03:00 daily.

set -e

USER_DATA_ROOT="$HOME/Library/Application Support/KUKANILEA"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    USER_DATA_ROOT="$HOME/.local/share/KUKANILEA"
fi

CORE_DB="$USER_DATA_ROOT/core.sqlite3"
AUTH_DB="$USER_DATA_ROOT/auth.sqlite3"

echo "[$(date -u)] Starting Maintenance..."

# 1. Vacuum Databases
for db in "$CORE_DB" "$AUTH_DB"; do
    if [[ -f "$db" ]]; then
        echo "Vacuuming $db..."
        sqlite3 "$db" "VACUUM;"
    fi
done

# 2. Clean temporary imports/uploads older than 7 days
IMPORT_DIR="$USER_DATA_ROOT/imports"
if [[ -d "$IMPORT_DIR" ]]; then
    echo "Cleaning up old imports..."
    find "$IMPORT_DIR" -type f -mtime +7 -delete
fi

echo "[$(date -u)] Maintenance complete."
