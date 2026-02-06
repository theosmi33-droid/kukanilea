# ADR-0004: LLM provider interface + Ollama integration strategy

## Status
Accepted

## Context
We need optional local LLM support without entangling core logic or requiring network access.

## Decision
- Define an `LLMProvider` interface with `generate(system_prompt, messages, context)`.
- Provide a deterministic Mock provider for local-first operation.
- Add an Ollama provider behind a feature flag; if unavailable, fall back to the Mock provider.
- System prompt is static and contains no secrets.
- Tool calls are never executed from LLM output.

## Consequences
- LLM usage is pluggable and safe by default.
- The product remains fully functional without Ollama.

## Alternatives Considered
- Hard-wire Ollama into orchestrator (rejected: breaks modularity).
