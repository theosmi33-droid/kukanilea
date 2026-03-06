# Main-Only Source Of Truth

KUKANILEA follows a strict main-only branching policy.

## Mandatory Rules

1. `main` is the only source of truth.
2. Every pull request must target `main`.
3. New work must start from the latest `origin/main`.
4. Do not chain new features on stale `codex/*` branches.

## Why

This keeps merge history understandable, avoids accidental branch drift, and
ensures quality gates run against the same baseline for every change.
