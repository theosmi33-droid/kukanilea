#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/.build_venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "[ci-parity] missing $PY; run scripts/ops/env_foundation_setup.sh first" >&2
  exit 3
fi

cd "$ROOT"

echo "[ci-parity] python version"
"$PY" --version

echo "[ci-parity] compile sanity"
"$PY" -m compileall app run.py kukanilea_app.py

echo "[ci-parity] vscode config policy"
"$PY" scripts/dev/enforce_vscode_configs.py --check

echo "[ci-parity] unit tests (without e2e)"
"$PY" -m pytest -q tests --ignore=tests/e2e

echo "[ci-parity] selected core tests"
"$PY" -m pytest -q tests/test_memory_system.py tests/test_rag_pipeline.py tests/test_lexoffice.py tests/test_error_ux.py

echo "[ci-parity] playwright e2e"
"$PY" -m pytest -q tests/e2e/test_ui_workflow.py || "$PY" -m pytest -q tests/e2e/test_ui_workflow.py --lf

echo "[ci-parity] done"
