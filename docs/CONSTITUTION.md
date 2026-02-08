# KUKANILEA Constitution

## Principles (Non‑Negotiable)
1. **DB is source of truth**: The database defines meaning, lifecycle, and access. Filesystem is the executor.
2. **Deny‑by‑default security**: RBAC + tenant scoping everywhere. Unknown roles are denied safely.
3. **Local‑first**: The product works fully offline. Connectors are optional and explicitly enabled.
4. **Prompt‑injection resistance**: All untrusted inputs (docs, mail, chat) are hostile. No tool execution without policy gate + provenance.
5. **Determinism**: Core workflows are reproducible and testable (idempotent jobs, stable outputs).
6. **Deterministic API envelopes**: Every API error responds with the ErrorEnvelope contract.
7. **Observability**: Critical paths emit logs, metrics, and audit events.
8. **Premium UX**: Consistent UI components, accessible defaults, zero broken states.
9. **Spec‑driven delivery**: Every major change updates specs, ADRs, and tests.

## Engineering Commitments
- Prefer small, mergeable commits.
- Keep APIs consistent with error envelopes and correlation IDs.
- Maintain tenant isolation in every query and filesystem access path.
