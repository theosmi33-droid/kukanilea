#!/usr/bin/env bash
set -euo pipefail

TENANT_ID="$(cat instance/tenant_id.txt)"
TIMESTAMP="$(date +%Y-%m-%d_%H-%M)"
TMP_DIR="/tmp/kukanilea_backup_${TENANT_ID}"
BACKUP_NAME="${TENANT_ID}_${TIMESTAMP}.tar.zst"
NAS_SHARE="//192.168.0.2/KUKANILEA-BACKUPS"
NAS_USER="${NAS_USER:-backupuser}"
NAS_PASS="${NAS_PASS:-}"

mkdir -p "$TMP_DIR"

sqlite3 instance/kukanilea.db .dump > "$TMP_DIR/db_dump.sql"
tar -C instance -cf - . | zstd -19 -T0 -o "${TMP_DIR}/${BACKUP_NAME}"

UPLOAD_FILE="${TMP_DIR}/${BACKUP_NAME}"
if command -v age >/dev/null 2>&1 && [[ -n "${NAS_PUBLIC_KEY:-}" ]]; then
  age -r "${NAS_PUBLIC_KEY}" -o "${TMP_DIR}/${BACKUP_NAME}.age" "${TMP_DIR}/${BACKUP_NAME}"
  UPLOAD_FILE="${TMP_DIR}/${BACKUP_NAME}.age"
fi

if command -v smbclient >/dev/null 2>&1; then
  smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "mkdir ${TENANT_ID}; cd ${TENANT_ID}; put ${UPLOAD_FILE} $(basename "$UPLOAD_FILE")"
else
  MOUNT_POINT="/mnt/kukanilea_nas"
  sudo mkdir -p "$MOUNT_POINT"
  sudo mount -t cifs "$NAS_SHARE" "$MOUNT_POINT" -o username="$NAS_USER",password="$NAS_PASS",vers=3.0
  sudo mkdir -p "${MOUNT_POINT}/${TENANT_ID}"
  sudo cp "$UPLOAD_FILE" "${MOUNT_POINT}/${TENANT_ID}/"
  sudo umount "$MOUNT_POINT"
fi

rm -rf "$TMP_DIR"
echo "Backup upload complete: $(basename "$UPLOAD_FILE")"
