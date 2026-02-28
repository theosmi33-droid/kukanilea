#!/bin/bash
# KUKANILEA Forensic Recovery Script
# Usage: ./scripts/dev/recover_file.sh <filename_pattern>

FILE=$1
if [ -z "$FILE" ]; then
  echo "Usage: $0 <filename_pattern>"
  echo "Example: $0 kukanilea_weather_plugin.py"
  exit 1
fi

# Search for the file in git history
COMMIT=$(git log --all --full-history --format="%H" -- "**/$FILE" | head -n 1)

if [ -z "$COMMIT" ]; then
  echo "Error: File '$FILE' not found in Git history."
  exit 1
fi

SHORT_HASH=$(echo $COMMIT | cut -c1-8)
echo "Found file in commit $SHORT_HASH"

mkdir -p quarantine
git show "$COMMIT:**/$FILE" > "quarantine/$FILE"

if [ $? -eq 0 ]; then
  echo "SUCCESS: File extracted to quarantine/$FILE"
  echo "Review it before moving to app/tools/ or app/plugins/"
else
  echo "Error: Failed to extract file."
  exit 1
fi
