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
RESTORE_TIMESTAMP="${RESTORE_TIMESTAMP:-$(date +%Y-%m-%d_%H-%M)}"
REPORT_FILE="${REPORT_FILE:-instance/operator_report_restore_${RESTORE_TIMESTAMP}.txt}"
DRY_RUN=0
MODE="nas"
START_EPOCH="$(date +%s)"
NAS_RETRIES="${NAS_RETRIES:-3}"
BASELINE_PATH="${BASELINE_PATH:-instance/restore_baseline.json}"
VALIDATION_SCRIPT="scripts/ops/restore_validation.py"

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
CHECKSUM_EXPECTED=""
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
METADATA_FILE="${BACKUP_FILE}.metadata.json"
SNAPSHOT_FILE="${BACKUP_FILE}.snapshot.json"
if [[ "$MODE" == "nas" ]] && command -v smbclient >/dev/null 2>&1; then
  if ! nas_get_with_retry "$BACKUP_FILE" "$LOCAL_FILE"; then
    MODE="degraded_local"
    log "WARN NAS download failed, switching to degraded local mode"
  else
    nas_get_with_retry "$CHECKSUM_FILE" "${TMP_DIR}/${CHECKSUM_FILE}" || true
    nas_get_with_retry "$METADATA_FILE" "${TMP_DIR}/${METADATA_FILE}" || true
    nas_get_with_retry "$SNAPSHOT_FILE" "${TMP_DIR}/${SNAPSHOT_FILE}" || true
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
  if [[ -f "$LOCAL_FALLBACK_DIR/$TENANT_ID/$METADATA_FILE" ]]; then
    cp "$LOCAL_FALLBACK_DIR/$TENANT_ID/$METADATA_FILE" "${TMP_DIR}/${METADATA_FILE}" || die "$EXIT_RUNTIME" "failed to copy local fallback metadata"
  fi
  if [[ -f "$LOCAL_FALLBACK_DIR/$TENANT_ID/$SNAPSHOT_FILE" ]]; then
    cp "$LOCAL_FALLBACK_DIR/$TENANT_ID/$SNAPSHOT_FILE" "${TMP_DIR}/${SNAPSHOT_FILE}" || die "$EXIT_RUNTIME" "failed to copy local fallback snapshot"
  fi
fi

if [[ -f "${TMP_DIR}/${CHECKSUM_FILE}" ]]; then
  CHECKSUM_EXPECTED="$(awk '{print $1}' "${TMP_DIR}/${CHECKSUM_FILE}" | head -n1)"
  CHECKSUM_ACTUAL="$(sha256_file "$LOCAL_FILE")"
  [[ "$CHECKSUM_EXPECTED" == "$CHECKSUM_ACTUAL" ]] || die "$EXIT_RUNTIME" "checksum mismatch for ${BACKUP_FILE}"
fi


INTEGRITY_STATUS="ok"
INTEGRITY_ISSUES=""
if [[ -f "${TMP_DIR}/${METADATA_FILE}" ]] && command -v python3 >/dev/null 2>&1; then
  if ! python3 - "$TENANT_ID" "$BACKUP_FILE" "$LOCAL_FILE" "${TMP_DIR}/${METADATA_FILE}" <<'PYMETA'
import json
import os
import sys
from pathlib import Path

tenant, backup_file, local_file, metadata_file = sys.argv[1:5]
meta = json.loads(Path(metadata_file).read_text(encoding="utf-8"))
issues = []
if meta.get("tenant_id") != tenant:
    issues.append("tenant mismatch")
if meta.get("backup_file") != backup_file:
    issues.append("backup file mismatch")
size = os.path.getsize(local_file)
if int(meta.get("backup_size_bytes", -1)) != int(size):
    issues.append("size mismatch")
if issues:
    print("; ".join(issues))
    raise SystemExit(1)
PYMETA
  then
    INTEGRITY_STATUS="failed"
    INTEGRITY_ISSUES="metadata mismatch"
  fi
else
  INTEGRITY_STATUS="warn_missing_metadata"
  INTEGRITY_ISSUES="metadata missing"
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

VALIDATION_STATUS="skipped"
VALIDATION_ISSUES=""
VALIDATION_FILE="${VALIDATION_FILE:-instance/restore_validation_after.json}"
mkdir -p "$(dirname "$VALIDATION_FILE")"
if command -v python3 >/dev/null 2>&1 && [[ -f "$VALIDATION_SCRIPT" ]]; then
  if [[ -f "${TMP_DIR}/${SNAPSHOT_FILE}" ]]; then
    BASELINE_PATH="${TMP_DIR}/${SNAPSHOT_FILE}"
  fi
  if [[ -f "$BASELINE_PATH" ]]; then
    if python3 "$VALIDATION_SCRIPT" --phase after --tenant "$TENANT_ID" --baseline "$BASELINE_PATH" > "$VALIDATION_FILE" 2>&1; then
      VALIDATION_STATUS="ok"
    else
      VALIDATION_STATUS="failed"
      VALIDATION_ISSUES="$(tr '\n' ' ' < "$VALIDATION_FILE" | cut -c1-240)"
    fi
  else
    VALIDATION_STATUS="warn_missing_baseline"
    VALIDATION_ISSUES="missing baseline: $BASELINE_PATH"
  fi
fi

END_EPOCH="$(date +%s)"
BACKUP_TS_EPOCH="$(date -d "$(echo "$BACKUP_FILE" | sed -E 's/.*_([0-9]{4}-[0-9]{2}-[0-9]{2})_([0-9]{2})-([0-9]{2}).*/\1 \2:\3:00/')" +%s 2>/dev/null || echo "$START_EPOCH")"
RTO_SECONDS="$((END_EPOCH - START_EPOCH))"
RPO_SECONDS="$((END_EPOCH - BACKUP_TS_EPOCH))"

{
  echo "report_version=1"
  echo "mode=$MODE"
  echo "tenant_id=$TENANT_ID"
  echo "backup_file=$BACKUP_FILE"
  if [[ -n "$CHECKSUM_EXPECTED" ]]; then
    echo "checksum_verified=true"
  else
    echo "checksum_verified=false"
  fi
  echo "integrity_check=$INTEGRITY_STATUS"
  echo "integrity_issues=$INTEGRITY_ISSUES"
  echo "metadata_file=$METADATA_FILE"
  echo "restore_validation=$VALIDATION_STATUS"
  echo "restore_validation_issues=$VALIDATION_ISSUES"
  echo "restore_validation_file=$VALIDATION_FILE"
  echo "restore_started_epoch=$START_EPOCH"
  echo "restore_completed_epoch=$END_EPOCH"
  echo "rto_seconds=$RTO_SECONDS"
  echo "rpo_seconds=$RPO_SECONDS"
} > "$REPORT_FILE"

if [[ "$INTEGRITY_STATUS" == "failed" ]]; then
  die "$EXIT_RUNTIME" "metadata integrity check failed"
fi
if [[ "$VALIDATION_STATUS" == "failed" ]]; then
  die "$EXIT_RUNTIME" "restore validation after compare failed"
fi

log "Restore complete (mode=$MODE validation=$VALIDATION_STATUS)."
