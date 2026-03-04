# PR/CI Orchestrator Report (2026-03-04)

## Open PRs & Activity
- **PR #215 (Merged)**: `feat(ops): add launch evidence gate and harden release checks` - **SUCCESS**.
- **No other open PRs detected** via `gh pr list`. 
- **Active Worktrees detected**:
  - `codex/einstellungen`: Ahead of main by 6 commits. Uncommitted changes in `app/routes/admin_tenants.py`.
  - `codex/projekte`: Uncommitted changes in logic files.
  - `codex/kalender`: Uncommitted changes in UI and routes.
  - `codex/dashboard`: Uncommitted changes.
  - `codex/upload`: Uncommitted changes.
  - `codex/messenger`: Uncommitted changes.
  - `codex/emailpostfach`: Uncommitted changes.
  - `codex/excel-docs-visualizer`: Massive diff (requires cleanup/commit).
  - `codex/floating-widget-chatbot`: Uncommitted changes.

## Failing Runs
- All recent runs for `main` and `codex/ops-launch-evidence-gate-20260304` are **SUCCESSFUL**.
- No failing runs detected in the last 30 entries.

## Merge-Blocker
- **Unpushed Work**: Domain worktrees have significant uncommitted/unpushed changes.
- **Divergence**: `codex/einstellungen` has 6 local commits that need pushing and a PR.
- **Artifact Pollution**: Many worktrees have large diffs against `main` including deletions of core files (e.g., `app/modules/time/logic.py`) which might indicate sync issues or accidental deletions during domain-focus.

## Next Actions (Prioritized)
1. **[LOW] Push & PR for Einstellungen**:
   ```bash
   git -C /Users/gensuminguyen/Kukanilea/worktrees/einstellungen push origin codex/einstellungen
   gh pr create --repo theosmi33-droid/kukanilea --base main --head codex/einstellungen --title "feat(einstellungen): system hardening and audit logging" --body "Finalized administrative audit trails and confirm-gates."
   ```
2. **[LOW] Cleanup and Commit for Kalender**:
   ```bash
   git -C /Users/gensuminguyen/Kukanilea/worktrees/kalender add .
   git -C /Users/gensuminguyen/Kukanilea/worktrees/kalender commit -m "feat(kalender): implement ICS export and dashboard reminders"
   git -C /Users/gensuminguyen/Kukanilea/worktrees/kalender push origin codex/kalender
   ```
3. **[LOW] Logic Fixes for Projekte/Tasks**:
   ```bash
   git -C /Users/gensuminguyen/Kukanilea/worktrees/projekte add .
   git -C /Users/gensuminguyen/Kukanilea/worktrees/projekte commit -m "fix(tasks): restore missing ProjectManager methods and harden transactions"
   git -C /Users/gensuminguyen/Kukanilea/worktrees/projekte push origin codex/projekte
   ```
4. **[URGENT] Verify Worktree Sync**: Investigate why `excel-docs-visualizer` and `upload` show deletions of core files that exist in `main`.
