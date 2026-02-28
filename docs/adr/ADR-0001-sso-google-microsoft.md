# ADR-0001: Google/Microsoft SSO (Post-Beta)

- Status: Accepted (Planning)
- Date: 2026-02-28
- Related: https://github.com/theosmi33-droid/kukanilea/issues/106

## Context
Enterprise customers require optional SSO for Google and Microsoft accounts. Current release includes only stub routes and no production OAuth flow.

## Decision
SSO will be implemented as a dedicated post-beta epic with explicit security controls:

1. OAuth 2.1/OIDC authorization code flow with PKCE (`S256`) and server-side `state` verification.
2. No tokens in localStorage/sessionStorage; server-side encrypted token store only.
3. Strict redirect URI allowlist per provider and environment.
4. Account linking requires explicit tenant + role mapping and audit trail entry.
5. Fallback login (`username/password`) remains available as break-glass.

## Security Requirements
- `state` and `nonce` are random, one-time, short-lived.
- PKCE verifier/challenge generated per login attempt.
- Provider tokens are encrypted at rest and scoped minimally.
- Session rotation on successful SSO login.
- CSRF protection on callback endpoint and no open redirects.

## Implementation Phases
1. Provider abstraction and config schema (`google`, `microsoft`).
2. Auth start/callback endpoints with PKCE + state.
3. User provisioning/linking policy and tenant-role mapping.
4. Audit log integration and tests.
5. Rollout behind feature flags.

## Test Requirements
- Unit tests for state/PKCE generation and callback validation.
- Integration tests for success/failure callbacks and replay protection.
- Security tests for tampered state/nonce and invalid redirect handling.

## Consequences
- SSO does not block beta launch.
- Existing local/offline auth remains default and mandatory fallback.
