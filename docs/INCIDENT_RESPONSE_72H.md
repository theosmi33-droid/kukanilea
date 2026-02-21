# INCIDENT_RESPONSE_72H

Date: 2026-02-21

## Purpose
Operational runbook for incident triage and 72-hour breach-readiness.

## Severity Model

- `SEV1`: confirmed security incident with potential confidentiality/integrity impact.
- `SEV2`: strong suspicion requiring immediate containment.
- `SEV3`: lower-risk anomaly requiring investigation.

## First Response Checklist

1. Open incident record with timestamp and owner.
2. Capture initial scope and affected components.
3. Preserve evidence (logs, hashes, request IDs, artifact paths).
4. Contain blast radius (disable path, revoke token, isolate system).
5. Assign communication lead and technical lead.

## 72-hour Readiness

- Maintain timeline of detection, decision, containment, and remediation actions.
- Keep regulator/customer communication templates ready.
- Ensure documented rationale if no notification is required.

## Evidence to Collect

- Request IDs and relevant event IDs.
- Security scan snapshots and CI run links.
- Artifact hashes and provenance references.
- User impact summary and remediation timeline.

## Output Artifacts

- Incident report markdown.
- Corrective action list with owners and due dates.
- Post-incident gate updates in `docs/RELEASE_GATES.md`.

## Reference

- https://gdpr-info.eu/art-33-gdpr/
