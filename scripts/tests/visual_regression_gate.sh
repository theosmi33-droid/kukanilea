#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-verify}"
ACTION_TARGET="${VR_ACTION_TARGET:-2400}"

if [[ "$MODE" == "baseline" ]]; then
  pytest -q tests/e2e/test_visual_regression_builder.py --update-snapshots
else
  VR_ACTION_TARGET="$ACTION_TARGET" pytest -q tests/e2e/test_visual_regression_builder.py
fi
