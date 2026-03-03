Mode: REVIEW_ONLY (strict). Do not edit files.

Mission:
- Follow `/Users/gensuminguyen/Kukanilea/kukanilea_production/docs/ai/GEMINI_MISSION_BRIEF.md`.
- Keep scope to guardrail verification only.

Task:
1) Verify current core guardrails status:
   - external CDN links in `app/templates` and `app/static/sim`
   - confirm-gate presence for `hx-post|hx-put|hx-patch|hx-delete`
   - scope only to:
     - `app/templates/layout.html`
     - `app/templates/admin_tenants.html`
     - `app/templates/audit_trail.html`
     - `app/templates/automation/rule_new.html`
     - `app/static/sim/kukanilea_mobile_node.html`
2) If gaps exist, provide minimal Codex patch plan (file + change), no execution.
3) Provide exact verification commands.
4) Stop immediately after this report (no extra exploration).

Output format:
- Status
- Findings P0/P1/P2
- Suggested patches (not applied)
- Verification commands
- NEEDS_CODEX: yes/no
