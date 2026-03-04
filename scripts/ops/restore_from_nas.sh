#!/usr/bin/env bash
set -euo pipefail

EXIT_USAGE=2
EXIT_DEPENDENCY=3
EXIT_RUNTIME=4

TENANT_ID="${TENANT_ID:-DEMO_TENANT}"
BACKUP_FILE="${BACKUP_FILE:-}"
NAS_SHARE="${NAS_SHARE:-//192.168.0.2/KUKANILEA-BACKUPS}"
NAS_USER="${NAS_USER:-backupuser}"
NAS_PASS="${NAS_PASS:-}"
TMP_DIR=""
LOCAL_FALLBACK_DIR="${LOCAL_FALLBACK_DIR:-instance/degraded_backups}"
REPORT_FILE="${REPORT_FILE:-instance/operator_report_restore_$(date +%Y-%m-%d_%H-%M).txt}"
DRY_RUN=0
MODE="nas"

usage() {
  cat <<'USAGE'
Usage: ./scripts/ops/restore_from_nas.sh [tenant_id] [backup_file] [--dry-run]

Options:
  --dry-run   Validate source backup resolution without extracting data
USAGE
}

log() {
  printf '[restore] %s\n' "$*"
}

die() {
  local code="$1"
  shift
  log "ERROR: $*"
  exit "$code"
}

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    --*) die "$EXIT_USAGE" "unknown option: $1" ;;
    *) POSITIONAL+=("$1") ;;
  esac
  shift
done

if [[ "${#POSITIONAL[@]}" -gt 0 ]]; then
  TENANT_ID="${POSITIONAL[0]}"
fi
if [[ "${#POSITIONAL[@]}" -gt 1 ]]; then
  BACKUP_FILE="${POSITIONAL[1]}"
fi
if [[ "${#POSITIONAL[@]}" -gt 2 ]]; then
  die "$EXIT_USAGE" "too many positional arguments"
fi

command -v tar >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "tar is required"
mkdir -p "$(dirname "$REPORT_FILE")"
mkdir -p instance
TMP_DIR="/tmp/kukanilea_restore_${TENANT_ID}_$$"
mkdir -p "$TMP_DIR"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ -z "$BACKUP_FILE" ]]; then
  if command -v smbclient >/dev/null 2>&1; then
    BACKUP_FILE="$(smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; ls" 2>/dev/null | awk '/\.tar\.(zst|gz)(\.age)?/{print $1}' | tail -n 1 || true)"
  fi
  if [[ -z "$BACKUP_FILE" ]]; then
    BACKUP_FILE="$(ls -1 "$LOCAL_FALLBACK_DIR/$TENANT_ID"/*.tar.* 2>/dev/null | awk -F/ '{print $NF}' | tail -n 1 || true)"
    MODE="degraded_local"
  fi
fi

[[ -n "$BACKUP_FILE" ]] || die "$EXIT_RUNTIME" "no backup file found for tenant=${TENANT_ID}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  {
    echo "mode=dry_run"
    echo "tenant_id=$TENANT_ID"
    echo "backup_file=$BACKUP_FILE"
    echo "rto_seconds=0"
    echo "rpo_seconds=0"
  } > "$REPORT_FILE"
  log "Dry-run complete: resolved backup_file=$BACKUP_FILE mode=$MODE"
  exit 0
fi

LOCAL_FILE="${TMP_DIR}/${BACKUP_FILE}"
if [[ "$MODE" == "nas" ]] && command -v smbclient >/dev/null 2>&1; then
  if ! smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; get ${BACKUP_FILE} ${LOCAL_FILE}"; then
    MODE="degraded_local"
    log "WARN NAS download failed, switching to degraded local mode"
  fi
fi

if [[ "$MODE" == "degraded_local" ]]; then
  [[ -f "$LOCAL_FALLBACK_DIR/$TENANT_ID/$BACKUP_FILE" ]] || die "$EXIT_RUNTIME" "local fallback backup missing: $LOCAL_FALLBACK_DIR/$TENANT_ID/$BACKUP_FILE"
  cp "$LOCAL_FALLBACK_DIR/$TENANT_ID/$BACKUP_FILE" "$LOCAL_FILE" || die "$EXIT_RUNTIME" "failed to copy local fallback backup"
fi

if [[ "$LOCAL_FILE" == *.age ]]; then
  command -v age >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "age binary required to decrypt .age backup"
  age -d -i "${AGE_PRIVATE_KEY_FILE:-$HOME/.config/kukanilea/age_key.txt}" -o "${TMP_DIR}/backup.tar.bin" "$LOCAL_FILE" || die "$EXIT_RUNTIME" "age decryption failed"
  LOCAL_FILE="${TMP_DIR}/backup.tar.bin"
fi

if [[ "$LOCAL_FILE" == *.tar.zst ]]; then
  command -v zstd >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "zstd required to restore .tar.zst backup"
  zstd -d "$LOCAL_FILE" -o "${TMP_DIR}/backup.tar" || die "$EXIT_RUNTIME" "zstd decompression failed"
  tar -xf "${TMP_DIR}/backup.tar" -C instance || die "$EXIT_RUNTIME" "tar extraction failed"
elif [[ "$LOCAL_FILE" == *.tar.gz ]]; then
  tar -xzf "$LOCAL_FILE" -C instance || die "$EXIT_RUNTIME" "tar.gz extraction failed"
else
  tar -xf "$LOCAL_FILE" -C instance || die "$EXIT_RUNTIME" "tar extraction failed"
fi

if [[ -f "${TMP_DIR}/db_dump.sql" ]] && command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 instance/auth.sqlite3 < "${TMP_DIR}/db_dump.sql" || die "$EXIT_RUNTIME" "sqlite restore failed"
fi

{
  echo "mode=$MODE"
  echo "tenant_id=$TENANT_ID"
  echo "backup_file=$BACKUP_FILE"
  echo "rto_seconds=0"
  echo "rpo_seconds=0"
} > "$REPORT_FILE"

log "Restore complete (mode=$MODE)."
