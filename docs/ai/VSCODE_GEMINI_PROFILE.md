# VS Code Gemini Profile (Token-Saving)

This profile keeps 4 VS Code workers productive under model/token limits.

## Model Routing

- Worker 1 (Core/P0 fixes): `gemini-2.5-pro` for reasoning-heavy route/merge fixes.
- Worker 2 (Domain hygiene): `gemini-2.5-flash` for fast repetitive checks.
- Worker 3 (Scope/overlap): `gemini-2.5-flash` for scripted workflows.
- Worker 4 (PR/CI monitor): `gemini-2.5-flash` for short API/status loops.

If `gemini-3-flash-preview` quota is exhausted, switch with:

```text
/model gemini-2.5-flash
```

For hard debugging sessions:

```text
/model gemini-2.5-pro
```

## Prompt Budget Rules

- Maximum one mission per prompt.
- Prefer 8-12 bullet steps, not long prose.
- Force short output:
  - "Return only: files changed, tests run, PASS/FAIL, next action."
- Always include explicit stop condition:
  - "Stop after first failing check and report root cause."

## Context Trimming Rules

- Never attach full `docs/reviews/*` history.
- Only reference:
  - latest 1 report per worker
  - current branch diff
  - relevant test file(s)
- Do not paste large logs; paste last 40 lines only.

## Safe Command Set (Auto-Approve candidates)

- `git status --short`
- `git diff --name-only`
- `pytest -q <target>`
- `python scripts/dev/check_domain_overlap.py ...`
- `bash scripts/orchestration/overlap_matrix_11.sh`
- `./scripts/ops/healthcheck.sh`

## Do Not Run

- `git reset --hard`
- `git checkout -- <file>`
- force push
- merge to `main` without explicit approval
