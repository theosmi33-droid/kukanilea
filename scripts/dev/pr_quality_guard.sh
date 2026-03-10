#!/usr/bin/env bash
set -euo pipefail

MAX_SCOPE_FILES="${MAX_SCOPE_FILES:-12}"
MAX_SCOPE_LOC="${MAX_SCOPE_LOC:-350}"
MIN_TESTS="${MIN_TESTS:-6}"
MAX_CHANGED_AREAS="${MAX_CHANGED_AREAS:-3}"
EVIDENCE_REPORT="${EVIDENCE_REPORT:-docs/reviews/codex/PR_QUALITY_GUARD_REPORT_20260305.md}"
BASE_BRANCH="${BASE_BRANCH:-${GITHUB_BASE_REF:-main}}"
CI_MODE=0
REPO_ROOT=""

SHARED_CORE_PATHS=(
  "app/web.py"
  "app/core/logic.py"
  "app/__init__.py"
  "app/db.py"
  "app/templates/layout.html"
)

usage() {
  cat <<USAGE
Usage: bash scripts/dev/pr_quality_guard.sh [--ci] [--base-branch <branch>] [--repo-root <path>]

Hard gates:
  - scope: changed files <= ${MAX_SCOPE_FILES} AND changed LOC <= ${MAX_SCOPE_LOC}
  - focused scope: changed areas <= ${MAX_CHANGED_AREAS}
  - test delta: >= ${MIN_TESTS}
  - evidence report exists: ${EVIDENCE_REPORT}
  - base and merge-base must resolve to origin/main (main-first)
  - shared-core hotspot edits are blocked by default
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ci)
      CI_MODE=1
      shift
      ;;
    --base-branch)
      BASE_BRANCH="${2:-}"
      shift 2
      ;;
    --repo-root)
      REPO_ROOT="${2:-}"
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

if [[ -z "$REPO_ROOT" ]]; then
  REPO_ROOT="$(git rev-parse --show-toplevel)"
fi
cd "$REPO_ROOT"

ORIGIN_MAIN_AVAILABLE=0
if git rev-parse --verify origin/main >/dev/null 2>&1; then
  ORIGIN_MAIN_AVAILABLE=1
  BASE_BRANCH="origin/main"
elif (( CI_MODE == 1 )); then
  echo "ERROR: origin/main not found. Main-first guard requires a synced origin/main." >&2
  exit 1
else
  echo "WARN: origin/main not found. Main-first freshness gate is skipped outside CI." >&2
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
MERGE_BASE="$(git merge-base HEAD "$BASE_BRANCH" 2>/dev/null || true)"

if [[ -z "$MERGE_BASE" ]]; then
  echo "ERROR: unable to resolve merge-base between HEAD and $BASE_BRANCH" >&2
  exit 1
fi

CHANGED_FILES=()
while IFS= read -r line; do
  CHANGED_FILES+=("$line")
done < <(git diff --name-only "$MERGE_BASE"..HEAD)
CHANGED_FILE_COUNT="${#CHANGED_FILES[@]}"

LOC_TOTAL="$(git diff --numstat "$MERGE_BASE"..HEAD | awk '{a+=$1; d+=$2} END {print (a+0)+(d+0)}')"
if [[ -z "$LOC_TOTAL" ]]; then LOC_TOTAL=0; fi

TEST_DELTA="$(git diff --numstat "$MERGE_BASE"..HEAD -- tests ':(glob)**/*test*.py' ':(glob)**/test_*.py' | awk '{a+=$1; d+=$2} END {print (a+0)+(d+0)}')"
if [[ -z "$TEST_DELTA" ]]; then TEST_DELTA=0; fi

EVIDENCE_OK=0
if [[ -f "$EVIDENCE_REPORT" ]]; then
  EVIDENCE_OK=1
fi

AREA_COUNT="$(printf '%s\n' "${CHANGED_FILES[@]}" | awk -F/ 'NF { if (NF==1) {print $1} else {print $1"/"$2} }' | sort -u | awk 'END {print NR+0}')"

SCOPE_OK=0
if (( CHANGED_FILE_COUNT <= MAX_SCOPE_FILES && LOC_TOTAL <= MAX_SCOPE_LOC )); then
  SCOPE_OK=1
fi

TEST_OK=0
if (( TEST_DELTA >= MIN_TESTS )); then
  TEST_OK=1
fi

FOCUS_OK=0
if (( AREA_COUNT <= MAX_CHANGED_AREAS )); then
  FOCUS_OK=1
fi

BASE_OK=1
if (( ORIGIN_MAIN_AVAILABLE == 1 )); then
  BASE_OK=0
  if [[ "$BASE_BRANCH" == "origin/main" && "$MERGE_BASE" == "$(git rev-parse origin/main)" ]]; then
    BASE_OK=1
  fi
fi

SHARED_CORE_HITS=()
for file in "${CHANGED_FILES[@]}"; do
  for hotspot in "${SHARED_CORE_PATHS[@]}"; do
    if [[ "$file" == "$hotspot" ]]; then
      SHARED_CORE_HITS+=("$file")
    fi
  done
done
SHARED_CORE_OK=1
if (( ${#SHARED_CORE_HITS[@]} > 0 )); then
  SHARED_CORE_OK=0
fi

status_line() {
  local key="$1" value="$2" result="$3"
  printf '%-24s %-8s %s\n' "$key" "$value" "$result"
}

echo "PR Quality Guard"
echo "  branch:        $CURRENT_BRANCH"
echo "  base branch:   $BASE_BRANCH"
echo "  merge base:    $MERGE_BASE"
echo
status_line "scope.changed_files" "$CHANGED_FILE_COUNT" "(max: $MAX_SCOPE_FILES and LOC <= $MAX_SCOPE_LOC)"
status_line "scope.changed_loc" "$LOC_TOTAL" "(max: $MAX_SCOPE_LOC and files <= $MAX_SCOPE_FILES)"
status_line "scope.changed_areas" "$AREA_COUNT" "(max: $MAX_CHANGED_AREAS)"
status_line "tests.delta" "$TEST_DELTA" "(min: $MIN_TESTS)"
status_line "evidence.report" "$EVIDENCE_REPORT" "(required)"
status_line "base.origin_main" "$BASE_BRANCH" "(must be origin/main)"
status_line "base.merge_base" "$MERGE_BASE" "(must equal origin/main tip)"
status_line "shared_core.hotspots" "${#SHARED_CORE_HITS[@]}" "(must be 0)"

if (( ${#SHARED_CORE_HITS[@]} > 0 )); then
  echo "shared_core.hits:"
  for line in "${SHARED_CORE_HITS[@]}"; do
    echo "  - $line"
  done
fi

FAILURES=()
(( SCOPE_OK == 1 )) || FAILURES+=("MAX_SCOPE gate failed: keep diff <=${MAX_SCOPE_FILES} files and <=${MAX_SCOPE_LOC} LOC")
(( FOCUS_OK == 1 )) || FAILURES+=("FOCUSED_SCOPE gate failed: changed areas ${AREA_COUNT} > ${MAX_CHANGED_AREAS}")
(( TEST_OK == 1 )) || FAILURES+=("MIN_TESTS gate failed: test delta ${TEST_DELTA} < ${MIN_TESTS}")
(( EVIDENCE_OK == 1 )) || FAILURES+=("Evidence report missing: ${EVIDENCE_REPORT}")
(( BASE_OK == 1 )) || FAILURES+=("Main-first base failed: merge-base must be current origin/main")
(( SHARED_CORE_OK == 1 )) || FAILURES+=("Shared-core hotspot touched: requires separate focused PR")

if (( ${#FAILURES[@]} > 0 )); then
  echo
  echo "PR_QUALITY_GUARD: FAIL"
  for f in "${FAILURES[@]}"; do
    echo " - $f"
    if (( CI_MODE == 1 )); then
      echo "::error::$f"
    fi
  done
  exit 1
fi

echo
echo "PR_QUALITY_GUARD: PASS"
