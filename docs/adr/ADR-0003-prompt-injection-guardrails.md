# ADR-0003: Prompt injection threat model + mitigations

## Status
Accepted

## Context
Chat and extracted document text are untrusted. Prompt injection attempts can request policy bypass, data exfiltration, or destructive actions.

## Decision
- Treat all user input and extracted text as UNTRUSTED.
- Detect instruction-like patterns (e.g., "ignore rules", "system prompt", "exfiltrate") and block with a safe response.
- Sanitize untrusted text before LLM summarization.
- Never execute tools based on LLM output; the Orchestrator decides and is policy-gated.
- Every blocked request creates an Audit event and a Task.

## Consequences
- Some user prompts may be rejected even if benign; UX must provide safe alternatives.
- Security posture is explicit and testable.

## Alternatives Considered
- Rely on LLM safety alone (rejected: insufficient and non-deterministic).
