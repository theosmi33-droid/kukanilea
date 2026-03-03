#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gensuminguyen/Kukanilea"
CORE="$ROOT/kukanilea_production"
REPORT_DIR="$CORE/docs/reviews/codex"

# locate the most recent master status file
REPORT=$(ls -1 "$REPORT_DIR"/FLEET_11TAB_MASTER_STATUS_*.md 2>/dev/null | sort | tail -n1 || true)
if [[ -z "$REPORT" ]]; then
    echo "[update_master_status] no existing master report found" >&2
    exit 1
fi

# run overlap matrix generator and capture output path
OVERLAP=$(bash "$CORE/scripts/orchestration/overlap_matrix_11.sh")
TS=$(date '+%Y-%m-%d %H:%M:%S')

# regenerate domain table directly via Python
python3 - "$REPORT" "$OVERLAP" <<'PY'
import sys
report=sys.argv[1]
overlap=sys.argv[2]
# parse overlap markdown rows
rows=[]
with open(overlap) as f:
    for line in f:
        line=line.strip()
        if line.startswith("| ") and not line.startswith("| Domain") and not line.startswith("|---"):
            parts=[p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 5:
                continue
            domain,branch,dirty,diff,ovlp = parts[:5]
            try:
                dirty_i=int(dirty)
            except ValueError:
                dirty_i=0
            try:
                diff_i=int(diff)
            except ValueError:
                diff_i=0
            status="clean"
            if dirty_i>0:
                status="dirty"
            elif diff_i>0:
                status="modified"
            rows.append(f"| {domain} | {branch} | {dirty_i} | {diff_i} | {ovlp} | n/a | {status} |")
# rebuild report, replacing section between ## Domains and the Hinweis note
content=open(report).read().splitlines()
out=[]
i=0
while i < len(content):
    line=content[i]
    out.append(line)
    if line.startswith("## Domains"):
        # skip old table until the Hinweis marker
        i+=1
        while i < len(content) and not content[i].startswith("> Hinweis"):
            i+=1
        # insert new table
        out.append("")
        out.append("| Domain | branch | dirty | diff(main...HEAD) | overlap | tests | status |")
        out.append("|---|---:|---:|---:|---:|---:|---:|")
        out.extend(rows)
        out.append("")
        continue
    i+=1
open(report,'w').write("\n".join(out))
PY

# append an update entry to the report
cat <<EOF >> "$REPORT"

### Update at $TS (automated)
- Overlap-Matrix regenerated: $OVERLAP
EOF

# optional: echo to stdout so caller can log it too
printf "[update_master_status] appended at %s, overlap file %s\n" "$TS" "$OVERLAP"
