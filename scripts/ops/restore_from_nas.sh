#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: ./scripts/ops/restore_from_nas.sh [--dry-run|--real-run] [--tenant TENANT_ID] [--backup BACKUP_FILE]

Environment:
  KUKANILEA_USER_DATA_ROOT   Restore target (default: ./instance)
  KUKANILEA_NAS_DIR          Local NAS source directory (default: ./evidence/nas)
USAGE
}

MODE="real"
TENANT_ID="${TENANT_ID:-${TENANT_DEFAULT:-KUKANILEA}}"
BACKUP_FILE="${BACKUP_FILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry" ;;
    --real-run) MODE="real" ;;
    --tenant) TENANT_ID="${2:?missing tenant value}"; shift ;;
    --backup) BACKUP_FILE="${2:?missing backup file}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
  shift
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_ROOT="${KUKANILEA_USER_DATA_ROOT:-${ROOT_DIR}/instance}"
NAS_DIR="${KUKANILEA_NAS_DIR:-${ROOT_DIR}/evidence/nas}"
TENANT_DIR="${NAS_DIR}/${TENANT_ID}"
RESTORE_META="${ROOT_DIR}/evidence/ops/last_restore_manifest.json"

if [[ ! -d "$TENANT_DIR" ]]; then
  echo "NAS tenant directory missing: $TENANT_DIR"
  exit 1
fi

if [[ -z "$BACKUP_FILE" ]]; then
  BACKUP_FILE="$(find "$TENANT_DIR" -maxdepth 1 -type f \( -name '*.tar.zst' -o -name '*.tar.gz' \) | sort | tail -n 1)"
else
  BACKUP_FILE="${TENANT_DIR}/${BACKUP_FILE}"
fi

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "No backup file found for tenant ${TENANT_ID}"
  exit 1
fi

if [[ "$MODE" == "dry" ]]; then
  echo "[DRY-RUN] restore backup=${BACKUP_FILE} -> data_root=${DATA_ROOT}"
  exit 0
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
mkdir -p "$DATA_ROOT" "${ROOT_DIR}/evidence/ops"

if [[ "$BACKUP_FILE" == *.tar.zst ]]; then
  zstd -d -q "$BACKUP_FILE" -o "$TMP_DIR/backup.tar"
  tar -xf "$TMP_DIR/backup.tar" -C "$TMP_DIR"
else
  tar -xzf "$BACKUP_FILE" -C "$TMP_DIR"
fi

if compgen -G "${DATA_ROOT}/*.sqlite3" > /dev/null; then
  mkdir -p "$DATA_ROOT/pre_restore"
  cp -a "${DATA_ROOT}"/*.sqlite3 "${DATA_ROOT}/pre_restore/" 2>/dev/null || true
fi

cp -a "$TMP_DIR"/. "$DATA_ROOT"/

METRICS_FILE="${BACKUP_FILE}.metrics.json"
if [[ -f "$METRICS_FILE" ]]; then
  cp "$METRICS_FILE" "${ROOT_DIR}/evidence/ops/last_restored_metrics.json"
fi

cat > "$RESTORE_META" <<JSON
{
  "tenant_id": "${TENANT_ID}",
  "backup_path": "${BACKUP_FILE}",
  "restored_at": "$(date +%Y%m%d_%H%M%S)"
}
JSON

echo "Restore completed from: ${BACKUP_FILE}"
