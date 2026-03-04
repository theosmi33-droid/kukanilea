# KUKANILEA Launch Evidence Run

- Timestamp: 2026-03-04T13:41:43+00:00
- Root: `/workspace/kukanilea`
- Host: `c879bbacbfb1`

## Repo Sync
`git fetch origin --prune && git rev-parse --short HEAD && git rev-parse --short origin/main`
```text
fatal: 'origin' does not appear to be a git repository
fatal: Could not read from remote repository.

Please make sure you have the correct access rights
and the repository exists.
```
## Open PRs
gh not installed
## Healthcheck-CI Alignment
`python scripts/ops/release_ci_alignment.py`
```text
pyenv: version `3.12.0' is not installed (set by /workspace/kukanilea/.python-version)
pyenv: python: command not found

The `python' command exists in these Python versions:
  3.10.19
  3.11.14
  3.12.12
  3.13.8
  3.14.0

Note: See 'pyenv help global' for tips on allowing both
      python2 and python3 to be found.
```
## VSCode Guardrails
`bash scripts/dev/vscode_guardrails.sh --check`
```text
warning: missing interpreter /workspace/kukanilea/.build_venv/bin/python (using /root/.pyenv/shims/python3)
vscode-configs: OK
```
## Overlap Matrix
`bash scripts/orchestration/overlap_matrix_11.sh`
```text
/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/reviews/codex/OVERLAP_MATRIX_11_20260304_134154.md
```
## Guardrails Verify
`python scripts/ops/verify_guardrails.py`
```text
pyenv: version `3.12.0' is not installed (set by /workspace/kukanilea/.python-version)
pyenv: python: command not found

The `python' command exists in these Python versions:
  3.10.19
  3.11.14
  3.12.12
  3.13.8
  3.14.0

Note: See 'pyenv help global' for tips on allowing both
      python2 and python3 to be found.
```
## White-Mode Scan
`rg -n "dark:|themeToggle|classList\.(add|toggle)\(("dark"|'dark')\)" app/templates app/static --glob "!app/static/vendor/**" --glob "!app/static/js/tailwindcss.min.js" || true`
```text
(no output)
```
## Color-Scheme Info Scan
`rg -n "prefers-color-scheme" app/templates app/static --glob "!app/static/vendor/**" --glob "!app/static/js/tailwindcss.min.js" || true`
```text
(no output)
```
## HTMX Shell Scan
`rg -n "hx-get|hx-target|hx-push-url" app/templates/layout.html app/templates -g "*.html" || true`
```text
app/templates/admin_tenants.html:15:        <form hx-post="/admin/tenants/add" hx-target="#validation-result" hx-swap="innerHTML" hx-confirm="Neuen Mandanten jetzt verknüpfen?" style="display: grid; grid-template-columns: 1fr 2fr auto; gap: 16px; align-items: flex-end;">
app/templates/components/outbound_status_panel.html:6:     hx-get="/api/outbound/status"
app/templates/components/system_status.html:2:     hx-get="/api/system/status"
app/templates/audit_trail.html:15:	                hx-target="#verify-status"
app/templates/partials/sidebar.html:9:      <a href="/dashboard" data-route="/dashboard" class="nav-link {{ 'active' if request.path in ['/', '/dashboard'] }}" hx-get="/dashboard" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:15:      <a href="/upload" data-route="/upload" class="nav-link {{ 'active' if request.path == '/upload' }}" hx-get="/upload" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:21:      <a href="/projects" data-route="/projects" class="nav-link {{ 'active' if request.path.startswith('/projects') }}" hx-get="/projects" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:27:      <a href="/tasks" data-route="/tasks" class="nav-link {{ 'active' if request.path.startswith('/tasks') }}" hx-get="/tasks" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:33:      <a href="/messenger" data-route="/messenger" class="nav-link {{ 'active' if request.path.startswith('/messenger') }}" hx-get="/messenger" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:39:      <a href="/email" data-route="/email" class="nav-link {{ 'active' if request.path.startswith('/email') or request.path.startswith('/mail') }}" hx-get="/email" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:45:      <a href="/calendar" data-route="/calendar" class="nav-link {{ 'active' if request.path.startswith('/calendar') }}" hx-get="/calendar" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:51:      <a href="/time" data-route="/time" class="nav-link {{ 'active' if request.path.startswith('/time') }}" hx-get="/time" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:57:      <a href="/visualizer" data-route="/visualizer" class="nav-link {{ 'active' if request.path.startswith('/visualizer') }}" hx-get="/visualizer" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
app/templates/partials/sidebar.html:63:      <a href="/settings" data-route="/settings" class="nav-link {{ 'active' if request.path.startswith('/settings') }}" hx-get="/settings" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML">
```

## Result Matrix

| Gate | Status | Note |
|---|---|---|
| Repo Sync | FAIL | git fetch/rev-parse failed |
| Open PRs | FAIL | gh missing |
| Healthcheck-CI Alignment | FAIL | healthcheck and CI workflow are not aligned |
| VSCode Guardrails | PASS | command succeeded |
| Overlap Matrix | FAIL | 11 fail markers in /Users/gensuminguyen/Kukanilea/kukanilea_production/docs/reviews/codex/OVERLAP_MATRIX_11_20260304_134154.md |
| Healthcheck | WARN | skipped by flag |
| Pytest | WARN | skipped by flag |
| Zero-CDN Scan | FAIL | guardrails verification failed |
| White-Mode Scan | PASS | no dark-mode toggles/patterns found |
| Color-Scheme Info Scan | PASS | no prefers-color-scheme references found |
| HTMX Shell Scan | PASS | htmx markers found |

## Fail Code Map

- 20: Repo Sync failed
- 21: Open PR gate failed
- 22: Main CI status gate failed
- 23: Healthcheck-CI alignment failed
- 24: Healthcheck gate failed
- 25: Pytest gate failed
- 26: Zero-CDN scan gate failed
- 27: Overlap matrix gate failed
- 29: Other gate failed

## Decision

**NO-GO**

- PASS: 4
- WARN: 2
- FAIL: 5
