# Beta Triage Policy (Week 1)

## Labels (required)
- `beta` on every beta item.
- Type: `bug` / `enhancement` / `question`
- Severity: `sev1` / `sev2` / `sev3`
- Area: `area-ui`, `area-workflows`, `area-ai`, `area-license`, `area-mail`, `area-docs`, `area-ci`
- Status: `needs-repro`, `needs-logs`, `ready`, `in-progress`, `blocked`, `fixed-in-main`, `needs-release`

## Severity guide
- `sev1`: security issue, data loss/corruption, license enforcement blocks reads, app fails to start, consistent 500 on core pages.
- `sev2`: core flow broken but workaround exists (CRM/Tasks/Docs/Workflows/AI partially unusable).
- `sev3`: UX polish, minor bugs, edge cases, wording.

## Intake checklist
1. Confirm version (for example `v1.0.0-beta.1`) and OS.
2. Capture exact repro steps and expected/actual behavior.
3. Confirm no PII is included.
4. Request logs/support bundle if needed (redacted).
5. Assign area + severity + status labels.

## Status transitions
- New -> `needs-repro` (default)
- Repro confirmed -> `ready`
- Work started -> `in-progress`
- Needs external input -> `blocked`
- Fixed merged -> `fixed-in-main`
- Awaiting beta patch release -> `needs-release`

## SLA targets (best effort)
- `sev1`: acknowledge < 24h, mitigation plan < 48h
- `sev2`: acknowledge < 48h
- `sev3`: weekly sweep

## Response templates
- Ask for repro:
  "Thanks. Please share exact steps to reproduce on vX.Y and your OS. If Ollama is used, include its status. Do not include PII."
- Ask for logs:
  "Please attach a redacted log excerpt or support-bundle path. Ensure no PII or secrets are included."
