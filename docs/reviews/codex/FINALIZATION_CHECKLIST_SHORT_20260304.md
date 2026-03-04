# KUKANILEA Finalization Checklist (Short, ~2 Min)

```bash
cd /Users/gensuminguyen/Kukanilea/kukanilea_production

echo '== Sync =='
git fetch origin --prune
echo "HEAD=$(git rev-parse --short HEAD)"
echo "ORIGIN_MAIN=$(git rev-parse --short origin/main)"

echo '== Open PRs =='
gh pr list --repo theosmi33-droid/kukanilea --state open

echo '== Main CI =='
gh run list --repo theosmi33-droid/kukanilea --limit 8 --json workflowName,displayTitle,headBranch,status,conclusion \
| jq -r '.[] | select(.headBranch=="main") | "\(.workflowName) | \(.status)/\(.conclusion) | \(.displayTitle)"'

echo '== Guardrails =='
bash scripts/dev/vscode_guardrails.sh --check

echo '== Health =='
./scripts/ops/healthcheck.sh

echo '== Decision =='
echo 'GO: no open PRs + all main runs success + guardrails OK + healthcheck pass'
```

## Optional Cleanup
```bash
pkill -f '/opt/homebrew/bin/Gemini' || true
pkill -f 'gemini-cli-security' || true
pkill -f 'gemini-cli-jules' || true
```
