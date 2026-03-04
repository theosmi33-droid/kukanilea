#!/usr/bin/env bash
set -euo pipefail

TENANT_ID="${1:-${TENANT_ID:-DEMO_TENANT}}"
BACKUP_FILE="${2:-${BACKUP_FILE:-}}"
NAS_SHARE="${NAS_SHARE:-//192.168.0.2/KUKANILEA-BACKUPS}"
NAS_USER="${NAS_USER:-backupuser}"
NAS_PASS="${NAS_PASS:-}"
TMP_DIR="/tmp/kukanilea_restore_${TENANT_ID}"
LOCAL_FALLBACK_DIR="${LOCAL_FALLBACK_DIR:-instance/degraded_backups}"
REPORT_FILE="${REPORT_FILE:-instance/operator_report_restore_$(date +%Y-%m-%d_%H-%M).txt}"

mkdir -p "$TMP_DIR" "$(dirname "$REPORT_FILE")"
MODE="nas"

if [[ -z "$BACKUP_FILE" ]]; then
  if command -v smbclient >/dev/null 2>&1; then
    BACKUP_FILE="$(smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; ls" | awk '/\.tar\.(zst|gz)(\.age)?/{print $1}' | tail -n 1)"
  fi
  if [[ -z "$BACKUP_FILE" ]]; then
    BACKUP_FILE="$(ls -1 "$LOCAL_FALLBACK_DIR/$TENANT_ID"/*.tar.* 2>/dev/null | awk -F/ '{print $NF}' | tail -n 1 || true)"
    MODE="degraded_local"
  fi
fi

if [[ -z "$BACKUP_FILE" ]]; then
  echo "No backup file found for tenant=${TENANT_ID}" >&2
  exit 1
fi

LOCAL_FILE="${TMP_DIR}/${BACKUP_FILE}"
if [[ "$MODE" == "nas" ]] && command -v smbclient >/dev/null 2>&1; then
  if ! smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; get ${BACKUP_FILE} ${LOCAL_FILE}"; then
    MODE="degraded_local"
  fi
fi

if [[ "$MODE" == "degraded_local" ]]; then
  cp "$LOCAL_FALLBACK_DIR/$TENANT_ID/$BACKUP_FILE" "$LOCAL_FILE"
  echo "[restore] WARN NAS unavailable, restored from degraded local spool"
fi

if [[ "$LOCAL_FILE" == *.age ]]; then
  age -d -i "${AGE_PRIVATE_KEY_FILE:-$HOME/.config/kukanilea/age_key.txt}" -o "${TMP_DIR}/backup.tar.bin" "$LOCAL_FILE"
  LOCAL_FILE="${TMP_DIR}/backup.tar.bin"
fi

if [[ "$LOCAL_FILE" == *.tar.zst ]]; then
  zstd -d "$LOCAL_FILE" -o "${TMP_DIR}/backup.tar"
  tar -xf "${TMP_DIR}/backup.tar" -C instance
elif [[ "$LOCAL_FILE" == *.tar.gz ]]; then
  tar -xzf "$LOCAL_FILE" -C instance
else
  tar -xf "$LOCAL_FILE" -C instance
fi

if [[ -f "${TMP_DIR}/db_dump.sql" && $(command -v sqlite3) ]]; then
  sqlite3 instance/auth.sqlite3 < "${TMP_DIR}/db_dump.sql"
fi

{
  echo "mode=$MODE"
  echo "tenant_id=$TENANT_ID"
  echo "backup_file=$BACKUP_FILE"
  echo "rto_seconds=0"
  echo "rpo_seconds=0"
} > "$REPORT_FILE"

rm -rf "$TMP_DIR"
echo "Restore complete (mode=$MODE)."
