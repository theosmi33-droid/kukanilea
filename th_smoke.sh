#!/usr/bin/env bash
set -euo pipefail

export TOPHANDWERK_API_KEY="${TOPHANDWERK_API_KEY:-change-me}"
API="http://127.0.0.1:5051"

echo "hello" > /tmp/th_test.txt

TOKEN="$(curl -s -H "X-API-Key: $TOPHANDWERK_API_KEY" \
  -F "file=@/tmp/th_test.txt" \
  "$API/upload" | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')"

echo "TOKEN=$TOKEN"

while true; do
  J="$(curl -s -H "X-API-Key: $TOPHANDWERK_API_KEY" "$API/progress/$TOKEN")"
  STATUS="$(python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])' <<<"$J")"
  PCT="$(python3 -c 'import sys,json; print(json.load(sys.stdin)["progress"])' <<<"$J")"
  echo "status=$STATUS progress=$PCT"
  [[ "$STATUS" == "READY" ]] && break
  [[ "$STATUS" == "ERROR" ]] && { echo "$J"; exit 1; }
  sleep 0.2
done

curl -s -H "X-API-Key: $TOPHANDWERK_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"kdnr":"1001","use_existing":"","name":"Test Kunde","addr":"Musterstraße 1","plzort":"10115 Berlin","doctype":"SONSTIGES","document_date":""}' \
  "$API/process/$TOKEN" | python3 -m json.tool
