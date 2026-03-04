#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/docs/status/KPI_SNAPSHOT_${STAMP}.md"
mkdir -p "$(dirname "$OUT")"

TMP_SEC="$(mktemp)"
TMP_PERF="$(mktemp)"

set +e
(cd "$ROOT" && python3 scripts/ops/zero_external_requests_scan.py) >"$TMP_SEC" 2>&1
SEC_RC=$?
(cd "$ROOT" && python3 scripts/ops/performance_gate.py) >"$TMP_PERF" 2>&1
PERF_RC=$?
set -e

cat > "$OUT" <<EOF
# KPI Snapshot

- Timestamp: $(date -Iseconds)
- Security Gate Exit Code: ${SEC_RC}
- Performance Gate Exit Code: ${PERF_RC}

## Security: Zero External Requests

\`python3 scripts/ops/zero_external_requests_scan.py\`

\`\`\`text
$(sed -n '1,200p' "$TMP_SEC")
\`\`\`

## Performance: Cold Start + Render Smoke

\`python3 scripts/ops/performance_gate.py\`

\`\`\`text
$(sed -n '1,200p' "$TMP_PERF")
\`\`\`
EOF

rm -f "$TMP_SEC" "$TMP_PERF"

echo "$OUT"
if [[ $SEC_RC -ne 0 || $PERF_RC -ne 0 ]]; then
  exit 1
fi
