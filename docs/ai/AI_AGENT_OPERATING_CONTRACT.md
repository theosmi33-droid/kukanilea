# KUKANILEA AI Agent Operating Contract

This contract is mandatory for terminal Gemini, VS Code AI assistants, and Codex-based workers.

## Mission

- Stabilize and finalize KUKANILEA as a local-first business OS.
- Prefer reliability, reproducibility, and evidence over feature expansion.
- Keep local and GitHub status synchronized.

## Non-Negotiable Rules

- Offline-first only, no external CDN assets in product rendering.
- White-mode only in Sovereign-11 shell scope.
- Respect domain ownership; do not edit shared-core paths from domain worktrees.
- Shared-core changes must go through scope request flow.
- No destructive git operations: no `git reset --hard`, no `git checkout --`, no force push.
- No merge to `main` without explicit approval.

## Shared-Core Protected Paths

- `app/web.py`
- `app/db.py`
- `app/templates/layout.html`
- global shell/static files under `app/static/` used across domains

## Required Preflight (Before Any Edit)

Run and report:

```bash
pwd -P
git branch --show-current
git status --porcelain
```

## Required Validation (After Changes)

Minimum:

```bash
./scripts/ops/healthcheck.sh
pytest -q
```

Domain work:

```bash
python scripts/dev/check_domain_overlap.py --reiter <domain> --files <changed_files> --json
```

## Output Contract

Always report:

- Files changed
- Tests run
- PASS/FAIL status
- Risks/blockers
- Next concrete step

## Reference Stack

Use these docs as primary context:

- `docs/ai/GEMINI_REFERENCE_STACK.md`
- `docs/TAB_OWNERSHIP_RULES.md`
- `docs/LAUNCH_EVIDENCE_CHECKLIST.md`
- `docs/SOVEREIGN_11_FINAL_PACKAGE.md` (if present in workspace/docs)
