#!/usr/bin/env bash
set -euo pipefail

CORE="/Users/gensuminguyen/Kukanilea/kukanilea_production"
LOGDIR="$CORE/logs"
mkdir -p "$LOGDIR"

while true; do
    bash "$CORE/scripts/orchestration/update_master_status.sh" >> "$LOGDIR/master_report.log" 2>&1
    # ensure overlap matrix also ran (script already calls overlap)
    date >> "$LOGDIR/master_report.log"
    sleep 900
done
