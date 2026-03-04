#!/usr/bin/env bash
set -euo pipefail

EXIT_USAGE=2
EXIT_DEPENDENCY=3
EXIT_RUNTIME=4

TENANT_ID="${TENANT_ID:-$(cat instance/tenant_id.txt 2>/dev/null || echo DEMO_TENANT)}"
TIMESTAMP="$(date +%Y-%m-%d_%H-%M)"
TMP_DIR="/tmp/kukanilea_backup_${TENANT_ID}"
NAS_SHARE="${NAS_SHARE:-//192.168.0.2/KUKANILEA-BACKUPS}"
NAS_USER="${NAS_USER:-backupuser}"
NAS_PASS="${NAS_PASS:-}"
LOCAL_FALLBACK_DIR="${LOCAL_FALLBACK_DIR:-instance/degraded_backups}"
REPORT_FILE="${REPORT_FILE:-instance/operator_report_backup_${TIMESTAMP}.txt}"
DB_PATH="${DB_PATH:-instance/auth.sqlite3}"
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage: ./scripts/ops/backup_to_nas.sh [--dry-run]

Options:
  --dry-run   Validate workflow without writing archive/upload
USAGE
}

log() {
  printf '[backup] %s\n' "$*"
}

die() {
  local code="$1"
  shift
  log "ERROR: $*"
  exit "$code"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "$EXIT_USAGE" "unknown argument: $1" ;;
  esac
  shift
done

command -v tar >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "tar is required"
mkdir -p "$(dirname "$REPORT_FILE")"

if [[ ! -d instance ]]; then
  die "$EXIT_RUNTIME" "instance directory is missing"
fi

log "tenant=${TENANT_ID} share=${NAS_SHARE} dry_run=${DRY_RUN}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  {
    echo "mode=dry_run"
    echo "tenant_id=$TENANT_ID"
    echo "backup_file=dry-run"
    echo "target=none"
    echo "rto_seconds=0"
    echo "rpo_seconds=0"
  } > "$REPORT_FILE"
  log "Dry-run complete: prerequisites validated, no archive written"
  exit 0
fi

mkdir -p "$TMP_DIR"

if [[ -f "$DB_PATH" ]] && command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_PATH" .dump > "$TMP_DIR/db_dump.sql" || die "$EXIT_RUNTIME" "sqlite dump failed for $DB_PATH"
fi

if command -v zstd >/dev/null 2>&1; then
  BACKUP_NAME="${TENANT_ID}_${TIMESTAMP}.tar.zst"
  tar -C instance -cf - . | zstd -19 -T0 -o "${TMP_DIR}/${BACKUP_NAME}" || die "$EXIT_RUNTIME" "zstd archive creation failed"
else
  BACKUP_NAME="${TENANT_ID}_${TIMESTAMP}.tar.gz"
  tar -C instance -czf "${TMP_DIR}/${BACKUP_NAME}" . || die "$EXIT_RUNTIME" "tar.gz archive creation failed"
fi

UPLOAD_FILE="${TMP_DIR}/${BACKUP_NAME}"
if command -v age >/dev/null 2>&1 && [[ -n "${NAS_PUBLIC_KEY:-}" ]]; then
  age -r "${NAS_PUBLIC_KEY}" -o "${TMP_DIR}/${BACKUP_NAME}.age" "${TMP_DIR}/${BACKUP_NAME}" || die "$EXIT_RUNTIME" "age encryption failed"
  UPLOAD_FILE="${TMP_DIR}/${BACKUP_NAME}.age"
fi

TARGET_MODE="nas"
TARGET_PATH=""
if command -v smbclient >/dev/null 2>&1; then
  if smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "mkdir ${TENANT_ID}; cd ${TENANT_ID}; put ${UPLOAD_FILE} $(basename "$UPLOAD_FILE")"; then
    TARGET_PATH="${NAS_SHARE}/${TENANT_ID}/$(basename "$UPLOAD_FILE")"
  else
    TARGET_MODE="degraded_local"
    log "WARN NAS upload failed, switching to degraded local mode"
  fi
else
  TARGET_MODE="degraded_local"
  log "WARN smbclient missing, switching to degraded local mode"
fi

if [[ "$TARGET_MODE" != "nas" ]]; then
  mkdir -p "$LOCAL_FALLBACK_DIR/$TENANT_ID"
  cp "$UPLOAD_FILE" "$LOCAL_FALLBACK_DIR/$TENANT_ID/" || die "$EXIT_RUNTIME" "failed to copy backup to local fallback"
  TARGET_PATH="$LOCAL_FALLBACK_DIR/$TENANT_ID/$(basename "$UPLOAD_FILE")"
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
log "Backup complete: $(basename "$UPLOAD_FILE") (mode=$TARGET_MODE)"
