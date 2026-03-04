#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: ./scripts/ops/backup_to_nas.sh [--dry-run|--real-run] [--tenant TENANT_ID]

Environment:
  KUKANILEA_USER_DATA_ROOT   Data root containing auth/core/license files (default: ./instance)
  KUKANILEA_NAS_DIR          Local NAS target directory for drills (default: ./evidence/nas)
USAGE
}

MODE="real"
TENANT_ID="${TENANT_ID:-${TENANT_DEFAULT:-KUKANILEA}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) MODE="dry" ;;
    --real-run) MODE="real" ;;
    --tenant) TENANT_ID="${2:?missing tenant value}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
  shift
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_ROOT="${KUKANILEA_USER_DATA_ROOT:-${ROOT_DIR}/instance}"
NAS_DIR="${KUKANILEA_NAS_DIR:-${ROOT_DIR}/evidence/nas}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
COMPRESS_EXT="tar.zst"
if ! command -v zstd >/dev/null 2>&1; then
  COMPRESS_EXT="tar.gz"
fi
BACKUP_BASENAME="${TENANT_ID}_${TIMESTAMP}.${COMPRESS_EXT}"
BACKUP_DIR="${NAS_DIR}/${TENANT_ID}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_BASENAME}"
METRICS_PATH="${BACKUP_PATH}.metrics.json"
MANIFEST_PATH="${ROOT_DIR}/evidence/ops/last_backup_manifest.json"

AUTH_DB="${KUKANILEA_AUTH_DB:-${DATA_ROOT}/auth.sqlite3}"
CORE_DB="${KUKANILEA_CORE_DB:-${DATA_ROOT}/core.sqlite3}"
LICENSE_FILE="${KUKANILEA_LICENSE_PATH:-${DATA_ROOT}/license.json}"
TRIAL_FILE="${KUKANILEA_TRIAL_PATH:-${DATA_ROOT}/trial.json}"

mkdir -p "$BACKUP_DIR" "${ROOT_DIR}/evidence/ops"

if [[ "$MODE" == "dry" ]]; then
  echo "[DRY-RUN] tenant=${TENANT_ID}"
  echo "[DRY-RUN] data_root=${DATA_ROOT}"
  echo "[DRY-RUN] backup_path=${BACKUP_PATH}"
  exit 0
fi

python3 "${ROOT_DIR}/scripts/ops/restore_validation.py" snapshot \
  --auth-db "$AUTH_DB" \
  --core-db "$CORE_DB" \
  --output "$METRICS_PATH"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/payload"
for fp in "$AUTH_DB" "$CORE_DB" "$LICENSE_FILE" "$TRIAL_FILE"; do
  if [[ -f "$fp" ]]; then
    cp "$fp" "$TMP_DIR/payload/$(basename "$fp")"
  fi
done

if compgen -G "${DATA_ROOT}/*.sqlite3*" > /dev/null; then
  cp -a "${DATA_ROOT}"/*.sqlite3* "$TMP_DIR/payload/" 2>/dev/null || true
fi

if [[ "$COMPRESS_EXT" == "tar.zst" ]]; then
  tar -C "$TMP_DIR/payload" -cf - . | zstd -q -T0 -19 -o "$BACKUP_PATH"
else
  tar -C "$TMP_DIR/payload" -czf "$BACKUP_PATH" .
fi

cat > "$MANIFEST_PATH" <<JSON
{
  "tenant_id": "${TENANT_ID}",
  "backup_path": "${BACKUP_PATH}",
  "metrics_path": "${METRICS_PATH}",
  "created_at": "${TIMESTAMP}"
}
JSON

echo "Backup completed: ${BACKUP_PATH}"
