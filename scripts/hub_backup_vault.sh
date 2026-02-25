#!/bin/bash
# KUKANILEA Hub Backup Vault
# Sichert die SQLite DB und Uploads auf die NAS Partition.

set -e

SOURCE_DB="instance/core.sqlite3"
BACKUP_DIR="${KUKANILEA_NAS_PATH:-/mnt/nas_vault}/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="kukanilea_backup_$TIMESTAMP.sqlite3"

mkdir -p "$BACKUP_DIR"

echo "🔐 Starte versiegeltes Backup: $BACKUP_NAME"

# 1. Sicherer Snapshot (SQLite .backup)
sqlite3 "$SOURCE_DB" ".backup '$BACKUP_DIR/$BACKUP_NAME'"

# 2. Integritäts-Versiegelung (SHA-256)
shasum -a 256 "$BACKUP_DIR/$BACKUP_NAME" > "$BACKUP_DIR/$BACKUP_NAME.sha256"

# 3. Logbucheintrag
echo "{"timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")", "file": "$BACKUP_NAME", "status": "SUCCESS"}" >> "internal_vault/backup_history.json"

# 4. Rotation: Behalte nur die letzten 24 Backups
ls -t "$BACKUP_DIR"/kukanilea_backup_*.sqlite3 | tail -n +25 | xargs -I {} rm {}

echo "✅ Backup abgeschlossen und auf NAS gespiegelt."
