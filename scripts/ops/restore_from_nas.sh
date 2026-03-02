#!/usr/bin/env bash
set -euo pipefail

# Safer restore: extracts into current project instance/ instead of root filesystem.
TENANT_ID="${1:?tenant_id required}"
BACKUP_FILE="${2:-}"
NAS_SHARE="//192.168.0.2/KUKANILEA-BACKUPS"
NAS_USER="${NAS_USER:-backupuser}"
NAS_PASS="${NAS_PASS:-}"
TMP_DIR="/tmp/kukanilea_restore_${TENANT_ID}"

mkdir -p "$TMP_DIR"

if [[ -z "$BACKUP_FILE" ]]; then
  if command -v smbclient >/dev/null 2>&1; then
    BACKUP_FILE="$(smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; ls" | awk '/\.tar\.zst(\.age)?/{print $1}' | tail -n 1)"
  else
    echo "Provide BACKUP_FILE when smbclient is unavailable."
    exit 1
  fi
fi

smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; get ${BACKUP_FILE} ${TMP_DIR}/${BACKUP_FILE}"
LOCAL_FILE="${TMP_DIR}/${BACKUP_FILE}"

if [[ "$LOCAL_FILE" == *.age ]]; then
  age -d -i "${AGE_PRIVATE_KEY_FILE:-$HOME/.config/kukanilea/age_key.txt}" -o "${TMP_DIR}/backup.tar.zst" "$LOCAL_FILE"
  LOCAL_FILE="${TMP_DIR}/backup.tar.zst"
fi

zstd -d "$LOCAL_FILE" -o "${TMP_DIR}/backup.tar"
mkdir -p instance

tar -xf "${TMP_DIR}/backup.tar" -C instance

if [[ -f "${TMP_DIR}/db_dump.sql" ]]; then
  sqlite3 instance/kukanilea.db < "${TMP_DIR}/db_dump.sql"
fi

echo "Restore complete (project-local instance/)."
