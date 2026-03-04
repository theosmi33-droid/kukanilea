#!/usr/bin/env bash
set -euo pipefail

TENANT_ID="${TENANT_ID:-$(cat instance/tenant_id.txt 2>/dev/null || echo DEMO_TENANT)}"
TIMESTAMP="$(date +%Y-%m-%d_%H-%M)"
TMP_DIR="/tmp/kukanilea_backup_${TENANT_ID}"
NAS_SHARE="${NAS_SHARE:-//192.168.0.2/KUKANILEA-BACKUPS}"
NAS_USER="${NAS_USER:-backupuser}"
NAS_PASS="${NAS_PASS:-}"
LOCAL_FALLBACK_DIR="${LOCAL_FALLBACK_DIR:-instance/degraded_backups}"
REPORT_FILE="${REPORT_FILE:-instance/operator_report_backup_${TIMESTAMP}.txt}"

echo "[backup] tenant=${TENANT_ID} share=${NAS_SHARE}"
mkdir -p "$TMP_DIR" "$(dirname "$REPORT_FILE")"

DB_PATH="${DB_PATH:-instance/auth.sqlite3}"
if [[ -f "$DB_PATH" && $(command -v sqlite3) ]]; then
  sqlite3 "$DB_PATH" .dump > "$TMP_DIR/db_dump.sql"
fi

if command -v zstd >/dev/null 2>&1; then
  BACKUP_NAME="${TENANT_ID}_${TIMESTAMP}.tar.zst"
  tar -C instance -cf - . | zstd -19 -T0 -o "${TMP_DIR}/${BACKUP_NAME}"
else
  BACKUP_NAME="${TENANT_ID}_${TIMESTAMP}.tar.gz"
  tar -C instance -czf "${TMP_DIR}/${BACKUP_NAME}" .
fi

UPLOAD_FILE="${TMP_DIR}/${BACKUP_NAME}"
if command -v age >/dev/null 2>&1 && [[ -n "${NAS_PUBLIC_KEY:-}" ]]; then
  age -r "${NAS_PUBLIC_KEY}" -o "${TMP_DIR}/${BACKUP_NAME}.age" "${TMP_DIR}/${BACKUP_NAME}"
  UPLOAD_FILE="${TMP_DIR}/${BACKUP_NAME}.age"
fi

TARGET_MODE="nas"
TARGET_PATH=""
if command -v smbclient >/dev/null 2>&1; then
  if smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "mkdir ${TENANT_ID}; cd ${TENANT_ID}; put ${UPLOAD_FILE} $(basename "$UPLOAD_FILE")"; then
    TARGET_PATH="${NAS_SHARE}/${TENANT_ID}/$(basename "$UPLOAD_FILE")"
  else
    TARGET_MODE="degraded_local"
  fi
else
  TARGET_MODE="degraded_local"
fi

if [[ "$TARGET_MODE" != "nas" ]]; then
  mkdir -p "$LOCAL_FALLBACK_DIR/$TENANT_ID"
  cp "$UPLOAD_FILE" "$LOCAL_FALLBACK_DIR/$TENANT_ID/"
  TARGET_PATH="$LOCAL_FALLBACK_DIR/$TENANT_ID/$(basename "$UPLOAD_FILE")"
  echo "[backup] WARN NAS unavailable, using degraded local mode: $TARGET_PATH"
fi

{
  echo "mode=$TARGET_MODE"
  echo "tenant_id=$TENANT_ID"
  echo "backup_file=$(basename "$UPLOAD_FILE")"
  echo "target=$TARGET_PATH"
  echo "rto_seconds=0"
  echo "rpo_seconds=0"
} > "$REPORT_FILE"

rm -rf "$TMP_DIR"
echo "Backup complete: $(basename "$UPLOAD_FILE") (mode=$TARGET_MODE)"
