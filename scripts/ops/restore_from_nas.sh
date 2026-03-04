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
START_EPOCH="$(date +%s)"
NAS_RETRIES="${NAS_RETRIES:-3}"
BASELINE_PATH="${BASELINE_PATH:-instance/restore_baseline.json}"
VALIDATION_ARTIFACT="${VALIDATION_ARTIFACT:-evidence/operations/restore_validation_latest.json}"

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

sha256_file() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
  else
    die "$EXIT_DEPENDENCY" "sha256sum/shasum is required"
  fi
}

nas_get_with_retry() {
  local remote_name="$1"
  local local_target="$2"
  local tries=1
  while [[ "$tries" -le "$NAS_RETRIES" ]]; do
    if smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; get ${remote_name} ${local_target}"; then
      return 0
    fi
    log "WARN NAS download attempt ${tries}/${NAS_RETRIES} failed for ${remote_name}"
    tries=$((tries + 1))
    sleep 1
  done
  return 1
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

if command -v python3 >/dev/null 2>&1 && [[ -f "scripts/ops/restore_validation.py" ]] && [[ ! -f "$BASELINE_PATH" ]] && [[ -f "instance/auth.sqlite3" ]]; then
  log "Baseline missing -> creating pre-restore snapshot at ${BASELINE_PATH}"
  python3 scripts/ops/restore_validation.py --phase before --tenant "$TENANT_ID" --baseline "$BASELINE_PATH" >/dev/null \
    || die "$EXIT_RUNTIME" "failed to create restore baseline"
fi

if [[ -z "$BACKUP_FILE" ]]; then
  if command -v smbclient >/dev/null 2>&1; then
    BACKUP_FILE="$(smbclient "$NAS_SHARE" -U "${NAS_USER}%${NAS_PASS}" -c "cd ${TENANT_ID}; ls" 2>/dev/null | awk '/\.tar\.(zst|gz)(\.age)?/{print $1}' | tail -n 1 || true)"
  fi
  if [[ -z "$BACKUP_FILE" ]]; then
    BACKUP_FILE="$(ls -1 "$LOCAL_FALLBACK_DIR/$TENANT_ID"/*.tar.* 2>/dev/null | awk -F/ '{print $NF}' | tail -n 1 || true)"
    MODE="degraded_local"
  fi
fi

if [[ -z "$BACKUP_FILE" ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    {
      echo "mode=dry_run_unresolved"
      echo "tenant_id=$TENANT_ID"
      echo "backup_file="
      echo "issue=no_backup_file_found"
      echo "rto_seconds=0"
      echo "rpo_seconds=0"
    } > "$REPORT_FILE"
    log "Dry-run complete: no backup file found for tenant=${TENANT_ID} (mode=${MODE})"
    exit 0
  fi
  die "$EXIT_RUNTIME" "no backup file found for tenant=${TENANT_ID}"
fi

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
CHECKSUM_EXPECTED=""
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [[ "$MODE" == "nas" ]] && command -v smbclient >/dev/null 2>&1; then
  if ! nas_get_with_retry "$BACKUP_FILE" "$LOCAL_FILE"; then
    MODE="degraded_local"
    log "WARN NAS download failed, switching to degraded local mode"
  else
    nas_get_with_retry "$CHECKSUM_FILE" "${TMP_DIR}/${CHECKSUM_FILE}" || true
  fi
elif [[ "$MODE" == "nas" ]]; then
  MODE="degraded_local"
  log "WARN smbclient missing, switching to degraded local mode"
fi

if [[ "$MODE" == "degraded_local" ]]; then
  [[ -f "$LOCAL_FALLBACK_DIR/$TENANT_ID/$BACKUP_FILE" ]] || die "$EXIT_RUNTIME" "local fallback backup missing: $LOCAL_FALLBACK_DIR/$TENANT_ID/$BACKUP_FILE"
  cp "$LOCAL_FALLBACK_DIR/$TENANT_ID/$BACKUP_FILE" "$LOCAL_FILE" || die "$EXIT_RUNTIME" "failed to copy local fallback backup"
  if [[ -f "$LOCAL_FALLBACK_DIR/$TENANT_ID/$CHECKSUM_FILE" ]]; then
    cp "$LOCAL_FALLBACK_DIR/$TENANT_ID/$CHECKSUM_FILE" "${TMP_DIR}/${CHECKSUM_FILE}" || die "$EXIT_RUNTIME" "failed to copy local fallback checksum"
  fi
fi

if [[ -f "${TMP_DIR}/${CHECKSUM_FILE}" ]]; then
  CHECKSUM_EXPECTED="$(awk '{print $1}' "${TMP_DIR}/${CHECKSUM_FILE}" | head -n1)"
  CHECKSUM_ACTUAL="$(sha256_file "$LOCAL_FILE")"
  [[ "$CHECKSUM_EXPECTED" == "$CHECKSUM_ACTUAL" ]] || die "$EXIT_RUNTIME" "checksum mismatch for ${BACKUP_FILE}"
fi

if [[ "$LOCAL_FILE" == *.age ]]; then
  command -v age >/dev/null 2>&1 || die "$EXIT_DEPENDENCY" "age binary required to decrypt .age backup"
  DECRYPTED_FILE="${TMP_DIR}/${BACKUP_FILE%.age}"
  age -d -i "${AGE_PRIVATE_KEY_FILE:-$HOME/.config/kukanilea/age_key.txt}" -o "$DECRYPTED_FILE" "$LOCAL_FILE" || die "$EXIT_RUNTIME" "age decryption failed"
  LOCAL_FILE="$DECRYPTED_FILE"
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

VALIDATION_STATUS="skipped"
VALIDATION_ISSUES=""
if command -v python3 >/dev/null 2>&1 && [[ -f "scripts/ops/restore_validation.py" ]]; then
  mkdir -p "$(dirname "$VALIDATION_ARTIFACT")"
  if VALIDATION_JSON="$(python3 scripts/ops/restore_validation.py --phase after --tenant "$TENANT_ID" --baseline "$BASELINE_PATH" 2>&1)"; then
    VALIDATION_STATUS="ok"
    printf '%s\n' "$VALIDATION_JSON" > "$VALIDATION_ARTIFACT"
  else
    VALIDATION_STATUS="failed"
    VALIDATION_ISSUES="$(printf '%s' "$VALIDATION_JSON" | tr '\n' ' ' | cut -c1-240)"
    printf '%s\n' "$VALIDATION_JSON" > "$VALIDATION_ARTIFACT"
  fi
fi

END_EPOCH="$(date +%s)"
BACKUP_TS_EPOCH="$(date -d "$(echo "$BACKUP_FILE" | sed -E 's/.*_([0-9]{4}-[0-9]{2}-[0-9]{2})_([0-9]{2})-([0-9]{2}).*/\1 \2:\3:00/')" +%s 2>/dev/null || echo "$START_EPOCH")"
RTO_SECONDS="$((END_EPOCH - START_EPOCH))"
RPO_SECONDS="$((END_EPOCH - BACKUP_TS_EPOCH))"

{
  echo "mode=$MODE"
  echo "tenant_id=$TENANT_ID"
  echo "backup_file=$BACKUP_FILE"
  echo "checksum_verified=${CHECKSUM_EXPECTED:+true}"
  echo "restore_validation=$VALIDATION_STATUS"
  echo "restore_validation_issues=$VALIDATION_ISSUES"
  echo "restore_validation_artifact=$VALIDATION_ARTIFACT"
  echo "restore_started_epoch=$START_EPOCH"
  echo "restore_completed_epoch=$END_EPOCH"
  echo "rto_seconds=$RTO_SECONDS"
  echo "rpo_seconds=$RPO_SECONDS"
} > "$REPORT_FILE"

log "Restore complete (mode=$MODE validation=$VALIDATION_STATUS)."
