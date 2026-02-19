# Beta Operations Runbook (Week 1)

## Channels
- Bugs/requests: GitHub Issues using the beta template.
- Questions: GitHub Discussions preferred (move non-actionable issues there).

## Daily routine (15-30 min)
1. Review new `beta` issues.
2. Apply labels: type, severity, area, status.
3. If details are missing, request repro/logs and mark `needs-repro` or `needs-logs`.
4. Escalate `sev1` to immediate mitigation and tracking issue.

## Weekly routine
- Sweep `sev3` backlog, remove duplicates, batch low-risk fixes.
- Refresh docs/runbooks when repeated confusion appears.

## Incident handling (`sev1`)
- Confirm scope and user impact.
- Post workaround/mitigation quickly.
- Patch via `docs/runbooks/HOTFIX.md` process.
- Add regression test before closing.

## Guardrails
- No PII/secrets in tickets, logs, or support bundles.
- No live license server URLs in CI (use local stub).
- No new runtime dependencies during beta ops.
