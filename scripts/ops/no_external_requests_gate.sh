#!/usr/bin/env bash
set -euo pipefail

# KUKANILEA Enterprise Gate: No External Requests
# Scans templates and static assets for http(s):// URLs not in allowlist.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXIT_OK=0
EXIT_FAIL=1

ALLOWLIST=(
    "http://127.0.0.1"
    "http://localhost"
    "https://example.com/hook"
    "https://kukanilea.de"
    "http://www.w3.org/2000/svg"
)

# Join allowlist into a regex pattern
ALLOW_REGEX=""
for item in "${ALLOWLIST[@]}"; do
    if [[ -z "$ALLOW_REGEX" ]]; then
        ALLOW_REGEX="$item"
    else
        ALLOW_REGEX="$ALLOW_REGEX|$item"
    fi
done

echo "[no-external-requests-gate] Scanning app/templates and app/static..."

# Find all http(s) URLs, excluding vendor assets and license files
# Use ripgrep (rg) if available, fallback to grep
FIND_CMD=""
if command -v rg >/dev/null 2>&1; then
    FIND_CMD="rg -o --glob '!**/vendor/**' --glob '!**/*.min.js' --glob '!**/LICENSE*' 'https?://[^\"'\'' ]+'"
else
    FIND_CMD="grep -roE --exclude-dir=vendor --exclude=*.min.js --exclude=LICENSE* 'https?://[^\"'\'' ]+'"
fi

EXTERNAL_URLS=$((cd "$ROOT" && eval "$FIND_CMD app/templates app/static") || true)

VIOLATIONS=""
if [[ -n "$EXTERNAL_URLS" ]]; then
    while IFS= read -r line; do
        URL=$(echo "$line" | cut -d: -f2-)
        FILE=$(echo "$line" | cut -d: -f1)
        
        if [[ ! "$URL" =~ ^($ALLOW_REGEX) ]]; then
            VIOLATIONS="${VIOLATIONS}${FILE}: ${URL}\n"
        fi
    done <<< "$EXTERNAL_URLS"
fi

if [[ -n "$VIOLATIONS" ]]; then
    echo "FAIL: External URLs found in assets:"
    echo -e "$VIOLATIONS"
    exit "$EXIT_FAIL"
fi

echo "PASS: No unauthorized external requests detected."
exit "$EXIT_OK"
