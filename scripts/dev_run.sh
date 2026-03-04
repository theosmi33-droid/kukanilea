#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUN_BOOTSTRAP=1
SEED_DATA=1
HOST="127.0.0.1"
PORT="5051"

die() {
  echo "[dev-run] ERROR: $*" >&2
  exit 2
}

usage() {
  cat <<'USAGE'
Usage: scripts/dev_run.sh [options] [-- <extra app args>]

Robuster One-Command Dev-Start:
- optional bootstrap (default: on)
- seed data (default: on)
- startet die App mit stabilem Interpreter aus .venv

Options:
  --skip-bootstrap    Skip scripts/dev_bootstrap.sh
  --skip-seed         Skip scripts/seed_dev_users.py
  --host <host>       Host for kukanilea_app.py (default: 127.0.0.1)
  --port <port>       Port for kukanilea_app.py (default: 5051)
  -h, --help          Show help
USAGE
}

EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-bootstrap) RUN_BOOTSTRAP=0 ;;
    --skip-seed) SEED_DATA=0 ;;
    --host)
      shift
      [[ $# -gt 0 ]] || die "missing value for --host"
      HOST="$1"
      ;;
    --port)
      shift
      [[ $# -gt 0 ]] || die "missing value for --port"
      PORT="$1"
      ;;
    --)
      shift
      EXTRA_ARGS=("$@")
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
  shift
done

if [[ "$RUN_BOOTSTRAP" -eq 1 ]]; then
  if [[ ! -f ".venv/.bootstrap_complete" ]]; then
    echo "[dev-run] bootstrap marker missing, running scripts/dev_bootstrap.sh"
    bash scripts/dev_bootstrap.sh
  else
    echo "[dev-run] bootstrap marker found (.venv/.bootstrap_complete)"
  fi
fi

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  die "python interpreter unavailable: $PYTHON (run scripts/dev_bootstrap.sh)"
fi

if [[ "$SEED_DATA" -eq 1 ]]; then
  "$PYTHON" scripts/seed_dev_users.py
fi

exec "$PYTHON" kukanilea_app.py --host "$HOST" --port "$PORT" "${EXTRA_ARGS[@]}"
