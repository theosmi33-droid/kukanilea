#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-$HOME/Tophandwerk_Kundenablage}"

echo "Base: $BASE"
echo

# Liste der Extensions + Count
find "$BASE" -type f \
  | sed -E 's/.*\.([^.\/]+)$/\1/' \
  | tr '[:upper:]' '[:lower:]' \
  | sort \
  | uniq -c \
  | sort -nr \
  | head -n 50

