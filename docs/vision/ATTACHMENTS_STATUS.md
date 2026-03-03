# KUKANILEA Attachments Status

Last updated: 2026-03-03
Scope: Vision and execution attachments synced into `docs/vision/`.

## Status Matrix
| File | Purpose | Status | Primary Owner | Used In |
|---|---|---|---|---|
| `KUKANILEA_TEAM_1PAGER.md` | Executive summary for team alignment | Active | Product/Core | Kickoff, stakeholder briefing |
| `KUKANILEA_FINAL_MASTER_PLAN_v3.md` | Master implementation plan | Active | Core Fleet Commander | Weekly planning, milestone tracking |
| `KUKANILEA_HARMONIE_INTEGRATIONSPFAD.md` | Integration architecture and rollout path | Active | Core + Domain Leads | Cross-domain integration reviews |
| `SOVEREIGN_11_FINAL_PACKAGE.md` | UI/UX + sovereignty rules baseline | Active | Frontend + Review | Sovereign compliance checks |
| `SOVEREIGN_11_QUICK_ACTION_CHECKLIST.md` | Tactical action checklist | Active | QA/Ops | Daily execution checklist |
| `SCOPE_REQUEST_EXAMPLE_DASHBOARD.md` | Scope request format reference | Active | Domain Owners | Shared-core change requests |
| `KUKANILEA_CLI_MASTER_ANLEITUNG.md` | Codex/Gemini CLI operating guide | Active | Automation/Ops | Agent operations and onboarding |
| `quick_start_cli.sh` | CLI bootstrap helper | Active (Local) | DevOps | Local CLI setup |

## Curation Notes
- Files are stored as repository references under `docs/vision/` for team visibility and reviewer access.
- Policy-sensitive external CDN examples from attachments are normalized to non-live placeholders where needed to satisfy repository guardrails.
- This folder is documentation-only; operational scripts still live under `scripts/`.

## Update Process
1. Replace files from source bundle only when a newer dated version exists.
2. Re-run repo guardrails:
   - `bash scripts/dev/vscode_guardrails.sh --check`
   - `./scripts/ops/healthcheck.sh`
3. Update this status file:
   - refresh `Last updated`
   - adjust `Status` and `Used In` columns
4. Open PR with title prefix: `docs(vision): ...`

## Reviewer Start Pack (`@zentrale-debug`)
Read in this order:
1. `KUKANILEA_TEAM_1PAGER.md`
2. `SOVEREIGN_11_QUICK_ACTION_CHECKLIST.md`
3. `KUKANILEA_FINAL_MASTER_PLAN_v3.md`
4. `SCOPE_REQUEST_EXAMPLE_DASHBOARD.md`
