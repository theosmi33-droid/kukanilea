#!/usr/bin/env bash
set -euo pipefail

MIN_SCOPE_FILES="${MIN_SCOPE_FILES:-7}"
MIN_SCOPE_LOC="${MIN_SCOPE_LOC:-200}"
MIN_TESTS="${MIN_TESTS:-6}"
EVIDENCE_REPORT="${EVIDENCE_REPORT:-docs/reviews/codex/PR_QUALITY_GUARD_REPORT_20260305.md}"
BASE_BRANCH="${BASE_BRANCH:-${GITHUB_BASE_REF:-main}}"
CI_MODE=0
REPO_ROOT=""

usage() {
  cat <<USAGE
Usage: bash scripts/dev/pr_quality_guard.sh [--ci] [--base-branch <branch>] [--repo-root <path>]

Hard gates:
  - scope: changed files >= ${MIN_SCOPE_FILES} OR changed LOC >= ${MIN_SCOPE_LOC}
  - test delta: >= ${MIN_TESTS}
  - evidence report exists: ${EVIDENCE_REPORT}
  - branch freshness: HEAD must include latest origin/main (behind=0 when origin/main exists)
  - branch lineage: HEAD must not equal or be based on another local codex/* branch
  - lane overlap check against local codex/* branches
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

if ! git rev-parse --verify "$BASE_BRANCH" >/dev/null 2>&1; then
  if git rev-parse --verify "origin/$BASE_BRANCH" >/dev/null 2>&1; then
    BASE_BRANCH="origin/$BASE_BRANCH"
  elif git rev-parse --verify origin/main >/dev/null 2>&1; then
    BASE_BRANCH=origin/main
  elif git rev-parse --verify main >/dev/null 2>&1; then
    BASE_BRANCH=main
  else
    BASE_BRANCH="$(git rev-list --max-parents=0 HEAD | tail -n 1)"
    echo "WARN: base branch not found, fallback to initial commit $BASE_BRANCH" >&2
  fi
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
MERGE_BASE="$(git merge-base HEAD "$BASE_BRANCH")"

MAIN_SYNC_OK=1
MAIN_SYNC_NOTE="origin/main not available locally"
if git show-ref --verify --quiet refs/remotes/origin/main; then
  MAIN_SYNC_OK=0
  COUNTS="$(git rev-list --left-right --count HEAD...origin/main 2>/dev/null || echo '0 0')"
  AHEAD="$(awk '{print $1}' <<<"$COUNTS")"
  BEHIND="$(awk '{print $2}' <<<"$COUNTS")"
  MAIN_SYNC_NOTE="ahead=${AHEAD}, behind=${BEHIND}"
  if [[ "$BEHIND" == "0" ]]; then
    MAIN_SYNC_OK=1
  fi
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

OVERLAP_COUNT=0
OVERLAP_LINES=()
CODEX_BRANCHES=()
BRANCH_CONTEXT_OK=1
BRANCH_CONTEXT_HITS=()
while IFS= read -r line; do
  CODEX_BRANCHES+=("$line")
done < <(git for-each-ref --format='%(refname:short)' refs/heads/codex/)
for BR in "${CODEX_BRANCHES[@]}"; do
  [[ -z "$BR" || "$BR" == "$CURRENT_BRANCH" ]] && continue

  if git merge-base --is-ancestor "$BR" HEAD >/dev/null 2>&1; then
    BRANCH_CONTEXT_OK=0
    BRANCH_CONTEXT_HITS+=("$BR")
  fi

  BR_MERGE_BASE="$(git merge-base "$BR" "$BASE_BRANCH" 2>/dev/null || true)"
  [[ -z "$BR_MERGE_BASE" ]] && continue
  BR_FILES=()
  while IFS= read -r line; do
    BR_FILES+=("$line")
  done < <(git diff --name-only "$BR_MERGE_BASE".."$BR")
  [[ "${#BR_FILES[@]}" -eq 0 ]] && continue

  BR_TMP="$(mktemp)"
  CUR_TMP="$(mktemp)"
  printf '%s\n' "${BR_FILES[@]}" | sort -u > "$BR_TMP"
  printf '%s\n' "${CHANGED_FILES[@]}" | sort -u > "$CUR_TMP"
  INTERSECTION=()
  while IFS= read -r line; do
    INTERSECTION+=("$line")
  done < <(comm -12 "$CUR_TMP" "$BR_TMP")
  rm -f "$BR_TMP" "$CUR_TMP"

  if [[ "${#INTERSECTION[@]}" -gt 0 ]]; then
    OVERLAP_COUNT=$((OVERLAP_COUNT + ${#INTERSECTION[@]}))
    OVERLAP_LINES+=("$BR: ${INTERSECTION[*]}")
  fi
done

SCOPE_OK=0
if (( CHANGED_FILE_COUNT >= MIN_SCOPE_FILES || LOC_TOTAL >= MIN_SCOPE_LOC )); then
  SCOPE_OK=1
fi

TEST_OK=0
if (( TEST_DELTA >= MIN_TESTS )); then
  TEST_OK=1
fi

OVERLAP_OK=1
if (( OVERLAP_COUNT > 0 )); then
  OVERLAP_OK=0
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
status_line "scope.changed_files" "$CHANGED_FILE_COUNT" "(min: $MIN_SCOPE_FILES or LOC >= $MIN_SCOPE_LOC)"
status_line "scope.changed_loc" "$LOC_TOTAL" "(min: $MIN_SCOPE_LOC or files >= $MIN_SCOPE_FILES)"
status_line "tests.delta" "$TEST_DELTA" "(min: $MIN_TESTS)"
status_line "evidence.report" "$EVIDENCE_REPORT" "(required)"
status_line "main.sync" "$MAIN_SYNC_NOTE" "(require behind=0 when origin/main exists)"
status_line "branch.context" "$BRANCH_CONTEXT_OK" "(must be 1; no codex/* ancestor)"
status_line "lane.overlap_count" "$OVERLAP_COUNT" "(must be 0)"

if (( BRANCH_CONTEXT_OK == 0 )); then
  echo "branch.context_hits:"
  for branch_hit in "${BRANCH_CONTEXT_HITS[@]}"; do
    echo "  - $branch_hit"
  done
fi

if (( OVERLAP_COUNT > 0 )); then
  echo "lane.overlaps:"
  for line in "${OVERLAP_LINES[@]}"; do
    echo "  - $line"
  done
fi

FAILURES=()
(( SCOPE_OK == 1 )) || FAILURES+=("MIN_SCOPE gate failed: need >=${MIN_SCOPE_FILES} changed files OR >=${MIN_SCOPE_LOC} LOC")
(( TEST_OK == 1 )) || FAILURES+=("MIN_TESTS gate failed: test delta ${TEST_DELTA} < ${MIN_TESTS}")
(( EVIDENCE_OK == 1 )) || FAILURES+=("Evidence report missing: ${EVIDENCE_REPORT}")
(( MAIN_SYNC_OK == 1 )) || FAILURES+=("Main sync gate failed: HEAD must include latest origin/main (behind=0)")
(( BRANCH_CONTEXT_OK == 1 )) || FAILURES+=("Branch context gate failed: HEAD includes commits from another local codex/* branch")
(( OVERLAP_OK == 1 )) || FAILURES+=("Lane overlap check failed: overlapping files with local codex/* branch(es)")

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
