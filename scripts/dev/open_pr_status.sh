#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-theosmi33-droid/kukanilea}"
STATE="${STATE:-open}"

usage() {
  cat <<USAGE
Usage: bash scripts/dev/open_pr_status.sh [--repo <owner/name>] [--state <open|closed|all>]

Checks PR status with graceful fallbacks:
1) gh CLI (if installed + authenticated)
2) GitHub REST API via curl (requires GITHUB_TOKEN or GH_TOKEN)

Prints a summary and exits with code:
  0: success (including "No open PRs")
  2: unable to query (missing tools/auth/network)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --state)
      STATE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

query_with_gh() {
  gh pr list --repo "$REPO" --state "$STATE" --json number,title,headRefName,baseRefName,isDraft,mergeStateStatus 2>/dev/null
}

query_with_api() {
  local token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
  if [[ -z "$token" ]]; then
    return 1
  fi

  curl -fsSL \
    -H "Authorization: Bearer $token" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/$REPO/pulls?state=$STATE&per_page=100"
}

JSON=""
SOURCE=""

if command -v gh >/dev/null 2>&1; then
  if JSON="$(query_with_gh)"; then
    SOURCE="gh"
  fi
fi

if [[ -z "$SOURCE" ]]; then
  if JSON="$(query_with_api)"; then
    SOURCE="api"
  fi
fi

if [[ -z "$SOURCE" ]]; then
  echo "Unable to query PRs for $REPO (need gh auth or GITHUB_TOKEN/GH_TOKEN + API access)." >&2
  exit 2
fi

python - "$REPO" "$STATE" "$SOURCE" <<'PY' <<<"$JSON"
import json
import sys

repo, state, source = sys.argv[1:4]
items = json.load(sys.stdin)

# Normalize gh output vs REST output.
rows = []
for p in items:
    rows.append({
        "number": p.get("number"),
        "title": p.get("title", ""),
        "head": p.get("headRefName") or (p.get("head") or {}).get("ref", ""),
        "base": p.get("baseRefName") or (p.get("base") or {}).get("ref", ""),
        "draft": p.get("isDraft", p.get("draft", False)),
        "merge_state": p.get("mergeStateStatus", p.get("mergeable_state", "unknown")),
    })

print(f"Repo: {repo}")
print(f"State: {state}")
print(f"Source: {source}")
print(f"Count: {len(rows)}")

if not rows:
    print("No open PRs")
    raise SystemExit(0)

for row in rows:
    draft = "draft" if row["draft"] else "ready"
    print(f"- #{row['number']} [{draft}] {row['head']} -> {row['base']}: {row['title']} (merge={row['merge_state']})")
PY
