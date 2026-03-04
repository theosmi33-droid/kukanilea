#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAT="text"

usage() {
  cat <<'EOF'
Usage: ./scripts/doctor.sh [--json]

Exit codes:
  0 = all checks passed
  2 = one or more checks failed
  64 = invalid arguments
EOF
}

if [[ "${1:-}" == "--json" ]]; then
  FORMAT="json"
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
elif [[ -n "${1:-}" ]]; then
  echo "[doctor] invalid argument: ${1}" >&2
  usage >&2
  exit 64
fi

REPORT_FILE="$(mktemp)"
set +e
KUKANILEA_REPO_ROOT="${ROOT_DIR}" python3 - <<'PY' >"${REPORT_FILE}"
from pathlib import Path
import os
from kukanilea.devtools.platform_hardening import collect_doctor_results, summarize_exit_code, to_json_payload

root = Path(os.environ['KUKANILEA_REPO_ROOT'])
results = collect_doctor_results(root)
print(to_json_payload(results))
raise SystemExit(summarize_exit_code(results))
PY
EXIT_CODE=$?
set -e
REPORT_JSON="$(cat "${REPORT_FILE}")"
rm -f "${REPORT_FILE}"

if [[ "${FORMAT}" == "json" ]]; then
  printf '%s\n' "${REPORT_JSON}"
else
  echo "[doctor] KUKANILEA platform diagnostics"
  REPORT_JSON="${REPORT_JSON}" python3 -c '
import json, os
payload = json.loads(os.environ["REPORT_JSON"])
for check in payload["checks"]:
    status = "OK" if check["ok"] else "FAIL"
    print(" - {check:<16} {status:>4} | {detail}".format(
        check=check["check"], status=status, detail=check["detail"]
    ))
print("overall: {}".format("OK" if payload["ok"] else "FAIL"))
'
fi

exit "${EXIT_CODE}"
