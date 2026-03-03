Mode: REVIEW_ONLY (strict). Do not edit files. Do not commit. Do not push.

Task:
- Perform a bounded Sovereign-11 core review for repo `theosmi33-droid/kukanilea`.
- Inspect only these local files:
  - /Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/layout.html
  - /Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/admin_tenants.html
  - /Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/audit_trail.html
  - /Users/gensuminguyen/Kukanilea/kukanilea_production/app/templates/automation/rule_new.html
  - /Users/gensuminguyen/Kukanilea/kukanilea_production/app/static/sim/kukanilea_mobile_node.html
  - /Users/gensuminguyen/Kukanilea/kukanilea_production/.github/workflows/*.yml
- Check exactly:
  1) Zero-CDN
  2) White-mode enforcement
  3) HTMX shell wiring
  4) Confirm-gates on write actions
  5) Merge-gate hints from workflows (if branch-protection itself is not queryable, mark as "Unklar")
- Stop immediately after producing the report.

Output format:
- Status: PASS | PASS with notes | FAIL
- Findings (P0/P1/P2)
- Files checked
- 5-step action plan (only if findings exist)
