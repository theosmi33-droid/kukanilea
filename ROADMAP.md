# Roadmap

## v1 Local Agent Orchestra
- App factory + blueprint structure.
- Deterministic agent orchestration (no LLM runtime).
- Tenant-safe auth and storage boundaries.
- Upload → Extract → Review → Archive flow.

## v2 Multi-Tenant Hosted
- Hosted auth provider + stronger RBAC.
- Tenant isolation at DB + storage layers.
- Audit log UI and export.

## v3 LLM Drop-in
- LLMProvider interface implementation.
- Optional provider selection (on-prem/cloud).
- Summarization + intent parsing extensions.
