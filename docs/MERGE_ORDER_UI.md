# UI Merge Order

## Scoped Ownership
- `dashboard`: dashboard screens and dashboard component partials.
- `upload`: upload/review templates.
- `messenger`: messenger template and floating chat widget assets.
- `kalender`: kalender-facing templates.
- `aufgaben_projekte`: kanban and project-specific templates.
- `shared_ui_shell`: layout/partials/skeletons and shared shell JavaScript.

Conflict rule: a UI file may map to exactly one owner lane. Shared shell files stay in `shared_ui_shell` and must merge last.

## Merge Queue
1. Domain-lane PRs (`dashboard`, `upload`, `messenger`, `kalender`, `aufgaben_projekte`) merge first.
2. Regenerate queue evidence and verify no lane overlap before every merge.
3. `shared_ui_shell` merges only after all queued domain-lane PRs are green.
4. If two PRs touch the same lane, merge oldest first and rebase newer branch.

## CI Gates
- Run `python scripts/dev/ui_conflict_preventer.py --base-branch origin/main` on pull requests.
- Enforce action budget: at least `2100` scoped ownership checks each run (configured with `validation_rounds` in `.github/policy/ui_conflict_guardrails.json`).
- Fail on unscoped UI changes or multi-owner path claims.
- Fail if this merge-order document loses required sections.
