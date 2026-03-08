#!/usr/bin/env bash
set -euo pipefail

# Lists only actionable GitHub Actions failures:
# - failures on main
# - failures on currently open PR head branches
#
# Usage:
#   scripts/ops/list_actionable_failures.sh
#   scripts/ops/list_actionable_failures.sh --all
#   scripts/ops/list_actionable_failures.sh --repo owner/name --limit 200

REPO="theosmi33-droid/kukanilea"
LIMIT=100
MODE="actionable"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --all)
      MODE="all"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required." >&2
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required." >&2
  exit 2
fi

FAILURES_JSON="$(gh run list -R "$REPO" --status failure --limit "$LIMIT" --json databaseId,workflowName,headBranch,displayTitle,createdAt,url)"

if [[ "$MODE" == "all" ]]; then
  echo "$FAILURES_JSON" | jq -r '
    if length == 0 then
      "No failed runs found."
    else
      .[] | "- [\(.headBranch)] \(.workflowName) | \(.displayTitle) | \(.createdAt) | \(.url)"
    end
  '
  exit 0
fi

ALLOW_BRANCHES_JSON="$(
  {
    echo "main"
    gh pr list -R "$REPO" --state open --limit 200 --json headRefName \
      | jq -r '.[].headRefName'
  } | awk 'NF' | sort -u | jq -R . | jq -s .
)"

ACTIONABLE_JSON="$(
  jq --argjson allow "$ALLOW_BRANCHES_JSON" '
    [ .[] | select((.headBranch // "") as $b | ($allow | index($b))) ]
  ' <<<"$FAILURES_JSON"
)"

TOTAL_FAILED="$(jq 'length' <<<"$FAILURES_JSON")"
ACTIONABLE_FAILED="$(jq 'length' <<<"$ACTIONABLE_JSON")"

echo "Repo: $REPO"
echo "Window: last $LIMIT failed runs"
echo "Total failed runs: $TOTAL_FAILED"
echo "Actionable failed runs (main + open PR branches): $ACTIONABLE_FAILED"
echo

if [[ "$ACTIONABLE_FAILED" -eq 0 ]]; then
  echo "No actionable failures."
  exit 0
fi

echo "$ACTIONABLE_JSON" | jq -r '
  .[] | "- [\(.headBranch)] \(.workflowName) | \(.displayTitle) | \(.createdAt) | \(.url)"
'

